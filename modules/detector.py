import cv2
import numpy as np
from ultralytics import YOLO
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import time
from collections import deque
import threading
import os
import hashlib
from pathlib import Path

import pygame
from gtts import gTTS


# ─────────────────────────────────────────
# Data Classes
# ─────────────────────────────────────────

@dataclass
class Detection:
    bbox: Tuple[int, int, int, int]
    label: str
    confidence: float
    center: Tuple[int, int] = field(init=False)

    def __post_init__(self):
        x1, y1, x2, y2 = self.bbox
        self.center = ((x1 + x2) // 2, (y1 + y2) // 2)


@dataclass
class PersonStatus:
    person: Detection
    has_helmet: bool
    has_vest: bool
    has_mask: bool
    in_zone: bool
    near_vehicle: bool
    violations: List[str] = field(default_factory=list)

    @property
    def is_compliant(self):
        return self.has_helmet and self.has_vest and not self.in_zone


@dataclass
class FrameResult:
    frame: np.ndarray
    persons: List[PersonStatus]
    alerts: List[str]
    fps: float
    violation_count: int
    safe_count: int
    zone_intrusion_count: int
    zone_source: str = "NONE"      # ← NEW: "MANUAL" | "AUTO:CONES" | "AUTO:SIGN" | "NONE"

    @property
    def total_workers(self):
        return len(self.persons)


# ─────────────────────────────────────────
# Voice Alert System — Zone Intrusion Only
# ─────────────────────────────────────────

class VoiceAlert:
    """
    Plays a spoken zone-intrusion warning via gTTS + pygame.
    Only fires when a worker enters the restricted zone, with a
    configurable repeat interval to prevent spamming.
    """

    ZONE_MESSAGE = "Alert! Unauthorized entry into restricted zone. Please leave immediately."

    def __init__(self, volume: float = 1.0, repeat_interval: int = 10):
        self.repeat_interval = repeat_interval   # seconds between repeated alerts
        self.last_spoken     = 0                 # unix timestamp of last playback
        self.speaking        = False
        self._queue          = []
        self._lock           = threading.Lock()
        self._volume         = volume
        self._enabled        = True              # live on/off toggle

        # Audio cache — avoid regenerating on every run
        self._cache_dir  = Path("storage/voice_cache")
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._audio_path = self._generate_audio()

        # Init pygame mixer
        pygame.mixer.init()
        pygame.mixer.music.set_volume(volume)

        # Background speaker thread (daemon — exits with main process)
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._speaker_loop, daemon=True)
        self._thread.start()
        print("✅ Zone voice alert ready (gTTS + pygame)")

    # ── Audio generation ──────────────────────────────────────────────────────

    def _generate_audio(self) -> str:
        """Generate and cache the zone-alert MP3. Returns path, or '' on error."""
        filename = self._cache_dir / f"{hashlib.md5(self.ZONE_MESSAGE.encode()).hexdigest()}.mp3"
        if not filename.exists():
            print("🎙️ Generating zone alert audio...")
            try:
                tts = gTTS(text=self.ZONE_MESSAGE, lang='en', slow=False)
                tts.save(str(filename))
                print(f"✅ Audio saved: {filename}")
            except Exception as e:
                print(f"⚠️ gTTS error: {e}")
                return ""
        return str(filename)

    # ── Speaker loop (runs in background thread) ──────────────────────────────

    def _speaker_loop(self):
        while not self._stop_event.is_set():
            if self._queue and self._enabled:
                with self._lock:
                    self._queue.pop(0)
                if self._audio_path and os.path.exists(self._audio_path):
                    try:
                        self.speaking = True
                        pygame.mixer.music.load(self._audio_path)
                        pygame.mixer.music.play()
                        while pygame.mixer.music.get_busy():
                            time.sleep(0.05)
                    except Exception as e:
                        print(f"⚠️ Playback error: {e}")
                    finally:
                        self.speaking = False
            elif self._queue and not self._enabled:
                # Voice disabled mid-queue — flush silently
                with self._lock:
                    self._queue.clear()
            else:
                time.sleep(0.05)

    # ── Public API ────────────────────────────────────────────────────────────

    def trigger_zone_alert(self):
        """Call every frame a zone intrusion is active. Respects repeat_interval."""
        if not self._enabled:
            return
        now = time.time()
        if now - self.last_spoken < self.repeat_interval:
            return  # still in cooldown
        self.last_spoken = now
        with self._lock:
            if len(self._queue) == 0:   # don't stack duplicate alerts
                self._queue.append("ZONE")
        print(f"🔊 Zone alert triggered (next in {self.repeat_interval}s)")

    def enable(self):
        """Instantly enable voice alerts."""
        self._enabled = True
        print("🔊 Voice alerts ENABLED")

    def disable(self):
        """Instantly disable voice + stop any active playback."""
        self._enabled = False
        with self._lock:
            self._queue.clear()
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass
        self.speaking = False
        print("🔇 Voice alerts DISABLED")

    def set_repeat_interval(self, seconds: int):
        """Update repeat interval live (e.g. from sidebar slider)."""
        self.repeat_interval = seconds
        print(f"⏱️ Zone alert interval set to {seconds}s")

    def set_volume(self, volume: float):
        """Update playback volume live."""
        self._volume = volume
        try:
            pygame.mixer.music.set_volume(volume)
        except Exception:
            pass

    def update_rate(self, rate: int):
        """No-op kept for API compatibility."""
        pass


# ─────────────────────────────────────────
# SafeSight Detector
# ─────────────────────────────────────────

class SafeSightDetector:

    PERSON_CLASSES    = {'Person'}
    HELMET_CLASSES    = {'Hardhat'}
    NO_HELMET_CLASSES = {'NO-Hardhat'}
    MASK_CLASSES      = {'Mask'}
    NO_MASK_CLASSES   = {'NO-Mask'}
    VEST_CLASSES      = {'Safety Vest'}
    NO_VEST_CLASSES   = {'NO-Safety Vest'}
    CONE_CLASSES      = {'Safety Cone'}
    VEHICLE_CLASSES   = {'vehicle'}
    MACHINERY_CLASSES = {'machinery'}

    CLASS_COLORS = {
        "Person":         (255, 105, 180),   # pink
        "Hardhat":        (  0, 255,   0),   # green  — compliant ✅
        "NO-Hardhat":     (  0,   0, 255),   # blue   — violation
        "Mask":           (  0, 255,   0),   # green
        "NO-Mask":        (  0, 100, 255),   # blue
        "Safety Vest":    (  0, 255, 255),   # cyan
        "NO-Safety Vest": (255,   0,   0),   # red    — violation
        "Safety Cone":    (  0, 165, 255),   # orange
        "vehicle":        (255,   0, 255),   # magenta
        "machinery":      (150,   0, 255),   # purple
    }

    # Zone source badge colours  (BGR)
    ZONE_SOURCE_COLORS = {
        "MANUAL":      (200, 200, 200),   # white-ish
        "AUTO:CONES":  (  0, 165, 255),   # orange  (same as cone colour)
        "AUTO:SIGN":   (  0, 255, 128),   # spring green
        "NONE":        (100, 100, 100),   # grey
    }

    def __init__(
        self,
        model_path: str,
        conf_threshold: float = 0.35,
        enable_voice: bool = True,
        sign_model_path: Optional[str] = None,    # ← NEW: path to sign_best.pt
        zone_mode: str = "auto",                  # ← NEW: "manual" | "auto"
    ):
        print("Loading SafeSight model...")

        self.model = YOLO(model_path)
        self.conf  = conf_threshold

        self.zone_polygon = None
        self._manual_zone = None          # stores the user-drawn polygon
        self.zone_source  = "NONE"        # tracks current active source
        self.zone_mode    = zone_mode     # "manual" or "auto"

        self.fps_buffer   = deque(maxlen=30)
        self.last_time    = time.time()

        # Voice alert — always instantiated so it can be toggled live
        self.voice_enabled = enable_voice
        self.voice = VoiceAlert(volume=1.0, repeat_interval=10) if enable_voice else None

        if not enable_voice and self.voice:
            self.voice.disable()

        # ── Auto zone detector (optional) ────────────────────────────────────
        self.zone_detector       = None
        self.zone_detector_error = None   # surfaced in UI by app.py
        if sign_model_path:
            try:
                from zone_detector import ZoneDetector
                self.zone_detector = ZoneDetector(sign_model_path=sign_model_path)
                print(f"✅ ZoneDetector ready (sign model: {sign_model_path})")
            except Exception as e:
                import traceback as _tb
                self.zone_detector_error = str(e)
                print(f"❌ ZoneDetector FAILED: {e}")
                print(_tb.format_exc())
        else:
            print("ℹ️  No sign model path provided — cone-only auto-detect available.")
            # We can still do cone hull without sign model; import lightweight version
            try:
                from zone_detector import ZoneDetector
                self.zone_detector = ZoneDetector.__new__(ZoneDetector)
                self.zone_detector.sign_model    = None
                self.zone_detector.sign_conf     = 0.40
                self.zone_detector.sign_expand_x = 2.5
                self.zone_detector.sign_expand_y = 2.5
                self.zone_detector.min_cones     = 3
                self.zone_detector.cone_padding  = 30
                self.zone_detector.prefer_cones  = True
                self.zone_detector._sign_classes_lower = set()
            except Exception:
                pass

        print("✅ Model loaded | classes:", list(self.model.names.values()))


    # ─────────────────────────────────────
    # Zone management
    # ─────────────────────────────────────

    def set_zone(self, points, source: str = "MANUAL"):
        """
        Set a zone polygon externally (manual input or auto-detected).

        points  — list of (x, y) tuples, or np.ndarray
        source  — "MANUAL" | "AUTO:CONES" | "AUTO:SIGN"
        """
        self.zone_polygon = np.array(points, dtype=np.int32)
        if source == "MANUAL":
            self._manual_zone = self.zone_polygon.copy()
        self.zone_source = source

    def clear_zone(self):
        """Remove the active zone polygon."""
        self.zone_polygon = None
        self._manual_zone = None
        self.zone_source  = "NONE"

    def set_zone_mode(self, mode: str):
        """Switch between 'manual' and 'auto' zone modes."""
        self.zone_mode = mode
        if mode == "manual" and self._manual_zone is not None:
            self.zone_polygon = self._manual_zone
            self.zone_source  = "MANUAL"
        elif mode == "auto":
            # Clear manual polygon — auto will update each frame
            self.zone_polygon = None
            self.zone_source  = "NONE"

    def _in_zone(self, point) -> bool:
        if self.zone_polygon is None:
            return False
        return cv2.pointPolygonTest(self.zone_polygon, point, False) >= 0


    # ─────────────────────────────────────
    # Auto zone update (called each frame)
    # ─────────────────────────────────────

    def _update_auto_zone(self, frame: np.ndarray, cones: list):
        """
        Runs ZoneDetector to infer zone from cones and/or sign model.
        Updates self.zone_polygon and self.zone_source in-place.
        No-op when zone_mode is "manual" or no zone_detector is loaded.
        """
        if self.zone_mode == "manual":
            # Manual mode: ensure manual polygon is active
            if self._manual_zone is not None and self.zone_polygon is None:
                self.zone_polygon = self._manual_zone
                self.zone_source  = "MANUAL"
            return

        # Auto mode
        if self.zone_detector is None:
            # No detector at all — try cone hull only
            if len(cones) >= 3:
                polygon = self._simple_cone_hull(cones)
                if polygon is not None:
                    self.zone_polygon = polygon
                    self.zone_source  = "AUTO:CONES"
                    return
            self.zone_polygon = None
            self.zone_source  = "NONE"
            return

        # Use sign model if available, else cone-only path
        if self.zone_detector.sign_model is not None:
            polygon, source = self.zone_detector.detect(frame, cones)
            # Use the bbox cached inside detect() — no second model call needed
            if source == "AUTO:SIGN":
                cached = getattr(self.zone_detector, "_last_detected_sign", None)
                self._last_sign_bbox = cached.bbox if cached else None
            else:
                self._last_sign_bbox = None
        else:
            polygon = self.zone_detector._cone_hull(cones)
            source  = "AUTO:CONES" if polygon is not None else "NONE"

        self.zone_polygon = polygon
        self.zone_source  = source

    def _simple_cone_hull(self, cones: list) -> Optional[np.ndarray]:
        """Minimal convex hull fallback (no ZoneDetector instance needed)."""
        centers = np.array([c.center for c in cones], dtype=np.float32)
        hull    = cv2.convexHull(centers)
        return hull.astype(np.int32)


    # ─────────────────────────────────────
    # FPS
    # ─────────────────────────────────────

    def _fps(self) -> float:
        now = time.time()
        fps = 1 / (now - self.last_time + 1e-6)
        self.last_time = now
        self.fps_buffer.append(fps)
        return sum(self.fps_buffer) / len(self.fps_buffer)


    # ─────────────────────────────────────
    # IOU
    # ─────────────────────────────────────

    def _iou(self, b1, b2) -> float:
        xa    = max(b1[0], b2[0])
        ya    = max(b1[1], b2[1])
        xb    = min(b1[2], b2[2])
        yb    = min(b1[3], b2[3])
        inter = max(0, xb - xa) * max(0, yb - ya)
        if inter == 0:
            return 0.0
        area1 = (b1[2] - b1[0]) * (b1[3] - b1[1])
        area2 = (b2[2] - b2[0]) * (b2[3] - b2[1])
        return inter / (area1 + area2 - inter + 1e-6)


    # ─────────────────────────────────────
    # Parse YOLO detections into buckets
    # ─────────────────────────────────────

    def _parse(self, results) -> dict:
        buckets = {
            "persons":    [],
            "helmets":    [],
            "no_helmets": [],
            "masks":      [],
            "no_masks":   [],
            "vests":      [],
            "no_vests":   [],
            "cones":      [],
            "vehicles":   [],
            "machinery":  [],
        }

        for box in results.boxes:
            label           = self.model.names[int(box.cls[0])]
            conf            = float(box.conf[0])
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            det             = Detection((x1, y1, x2, y2), label, conf)

            if   label in self.PERSON_CLASSES:    buckets["persons"].append(det)
            elif label in self.HELMET_CLASSES:    buckets["helmets"].append(det)
            elif label in self.NO_HELMET_CLASSES: buckets["no_helmets"].append(det)
            elif label in self.MASK_CLASSES:      buckets["masks"].append(det)
            elif label in self.NO_MASK_CLASSES:   buckets["no_masks"].append(det)
            elif label in self.VEST_CLASSES:      buckets["vests"].append(det)
            elif label in self.NO_VEST_CLASSES:   buckets["no_vests"].append(det)
            elif label in self.CONE_CLASSES:      buckets["cones"].append(det)
            elif label in self.VEHICLE_CLASSES:   buckets["vehicles"].append(det)
            elif label in self.MACHINERY_CLASSES: buckets["machinery"].append(det)

        return buckets


    # ─────────────────────────────────────
    # PPE Compliance check per person
    # ─────────────────────────────────────

    def _check_person(self, person: Detection, buckets: dict) -> PersonStatus:
        p = person.bbox

        helmet = any(self._iou(p, h.bbox) > 0.05 for h in buckets["helmets"])
        vest   = any(self._iou(p, v.bbox) > 0.05 for v in buckets["vests"])
        mask   = any(self._iou(p, m.bbox) > 0.05 for m in buckets["masks"])

        # Negative detections override positives
        if any(self._iou(p, h.bbox) > 0.05 for h in buckets["no_helmets"]): helmet = False
        if any(self._iou(p, v.bbox) > 0.05 for v in buckets["no_vests"]):   vest   = False
        if any(self._iou(p, m.bbox) > 0.05 for m in buckets["no_masks"]):   mask   = False

        in_zone      = self._in_zone(person.center)
        near_vehicle = any(self._iou(p, v.bbox) > 0.05 for v in buckets["vehicles"])

        violations = []
        if not helmet:   violations.append("NO HELMET")
        if not vest:     violations.append("NO VEST")
        if not mask:     violations.append("NO MASK")
        if in_zone:      violations.append("ZONE INTRUSION")
        if near_vehicle: violations.append("VEHICLE NEARBY")

        return PersonStatus(person, helmet, vest, mask, in_zone, near_vehicle, violations)


    # ─────────────────────────────────────
    # Drawing helpers
    # ─────────────────────────────────────

    def _draw_boxes(self, frame: np.ndarray, buckets: dict) -> np.ndarray:
        # Draw restricted zone overlay
        if self.zone_polygon is not None and len(self.zone_polygon) >= 3:
            color   = self.ZONE_SOURCE_COLORS.get(self.zone_source, (0, 0, 255))
            overlay = frame.copy()
            cv2.fillPoly(overlay, [self.zone_polygon], color)
            cv2.addWeighted(overlay, 0.25, frame, 0.75, 0, frame)
            cv2.polylines(frame, [self.zone_polygon], True, color, 2)

            # Zone label + source badge
            pts = self.zone_polygon
            cx  = int(pts[:, 0].mean()) if pts.ndim == 2 else int(pts[:, 0, 0].mean())
            cy  = int(pts[:, 1].mean()) if pts.ndim == 2 else int(pts[:, 0, 1].mean())
            cv2.putText(
                frame, "RESTRICTED ZONE", (cx - 80, cy - 12),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2,
            )
            # Source badge below zone label
            badge = f"[{self.zone_source}]"
            cv2.putText(
                frame, badge, (cx - 40, cy + 14),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1,
            )

        # Auto-zone construction overlays
        if self.zone_source == "AUTO:CONES":
            self._draw_cone_hull_overlay(frame, buckets["cones"])
        elif self.zone_source == "AUTO:SIGN":
            self._draw_sign_zone_overlay(frame)

        # Draw bounding boxes + labels for all detections
        for key in buckets:
            for det in buckets[key]:
                x1, y1, x2, y2 = det.bbox
                color = self.CLASS_COLORS.get(det.label, (255, 255, 255))
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                cv2.putText(
                    frame,
                    f"{det.label} {det.confidence:.2f}",
                    (x1, y1 - 6),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.45, color, 2,
                )
        return frame

    def _draw_voice_indicator(self, frame: np.ndarray) -> np.ndarray:
        """Show a MIC indicator in the top-right corner while voice is speaking."""
        if self.voice and self.voice.speaking:
            h, w = frame.shape[:2]
            cv2.circle(frame, (w - 30, 30), 14, (0, 200, 255), -1)
            cv2.putText(
                frame, "MIC", (w - 46, 35),
                cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 0, 0), 1,
            )
        return frame


    # ─────────────────────────────────────
    # Cone hull visualisation
    # ─────────────────────────────────────

    def _draw_cone_hull_overlay(self, frame: np.ndarray, cones: list) -> np.ndarray:
        """
        Visualises how the AUTO:CONES zone was constructed:

          1. Filled dot at every cone center   — shows which cones contributed
          2. Dashed spoke from each center to  — shows the hull is built from them
             the nearest hull vertex
          3. Cone count badge (top-left of     — quick sanity check
             the hull bounding box)

        Only called when zone_source == "AUTO:CONES" and hull exists.
        The hull polygon itself is already drawn by _draw_boxes().
        """
        if self.zone_polygon is None or len(cones) == 0:
            return frame

        CONE_DOT   = (  0, 165, 255)   # orange — same as CLASS_COLORS["Safety Cone"]
        SPOKE_COL  = (  0, 165, 255)
        COUNT_COL  = (  0, 165, 255)

        # Normalise hull to a flat (N, 2) array regardless of cv2.convexHull shape
        hull_pts = self.zone_polygon
        if hull_pts.ndim == 3:                       # cv2 returns (N, 1, 2)
            hull_pts = hull_pts.reshape(-1, 2)

        # ── 1. Spoke from each cone center to nearest hull vertex ────────────
        for cone in cones:
            cx, cy = cone.center

            # Find closest hull vertex
            dists = np.linalg.norm(hull_pts - np.array([cx, cy]), axis=1)
            nearest = hull_pts[int(np.argmin(dists))]
            vx, vy = int(nearest[0]), int(nearest[1])

            # Draw dashed line manually (cv2 has no native dash support)
            _draw_dashed_line(frame, (cx, cy), (vx, vy), SPOKE_COL,
                              thickness=1, dash_len=6, gap_len=4)

        # ── 2. Filled dot at each cone center ───────────────────────────────
        for cone in cones:
            cx, cy = cone.center
            cv2.circle(frame, (cx, cy), 6, CONE_DOT, -1)          # filled dot
            cv2.circle(frame, (cx, cy), 6, (0, 0, 0), 1)           # thin black ring

        # ── 3. Cone count badge at top-left of hull bounding box ─────────────
        x_min = int(hull_pts[:, 0].min())
        y_min = int(hull_pts[:, 1].min())
        badge = f"{len(cones)} cones"
        (tw, th), _ = cv2.getTextSize(badge, cv2.FONT_HERSHEY_SIMPLEX, 0.42, 1)
        pad = 4
        bx1, by1 = x_min, max(0, y_min - th - pad * 2 - 2)
        bx2, by2 = x_min + tw + pad * 2, y_min - 2
        cv2.rectangle(frame, (bx1, by1), (bx2, by2), CONE_DOT, -1)
        cv2.putText(
            frame, badge,
            (bx1 + pad, by2 - pad),
            cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 0), 1,
        )

        return frame


    def _draw_sign_zone_overlay(self, frame: np.ndarray) -> np.ndarray:
        """
        Visualises the AUTO:SIGN zone expansion:

          • Dashed rectangle showing the original sign bounding box
            (stored in self._last_sign_bbox when sign detection ran)
          • Arrows pointing outward from each side of the sign bbox
            to the expanded zone edge — makes the expansion factor obvious

        Only called when zone_source == "AUTO:SIGN".
        No-op if _last_sign_bbox was never set.
        """
        sign_bbox = getattr(self, "_last_sign_bbox", None)
        if sign_bbox is None or self.zone_polygon is None:
            return frame

        sx1, sy1, sx2, sy2 = sign_bbox
        SIGN_COL = (0, 255, 128)    # spring-green — matches ZONE_SOURCE_COLORS["AUTO:SIGN"]

        # ── Original sign bbox (dashed) ──────────────────────────────────────
        _draw_dashed_rect(frame, (sx1, sy1), (sx2, sy2), SIGN_COL,
                          thickness=1, dash_len=8, gap_len=5)
        cv2.putText(
            frame, "sign",
            (sx1, sy1 - 5),
            cv2.FONT_HERSHEY_SIMPLEX, 0.38, SIGN_COL, 1,
        )

        # ── Expansion arrows (sign edge → zone edge, one per side) ───────────
        hull = self.zone_polygon
        if hull.ndim == 3:
            hull = hull.reshape(-1, 2)
        zx1, zy1 = int(hull[:, 0].min()), int(hull[:, 1].min())
        zx2, zy2 = int(hull[:, 0].max()), int(hull[:, 1].max())

        scx = (sx1 + sx2) // 2
        scy = (sy1 + sy2) // 2

        # Four outward arrows: left, right, top, bottom
        _draw_arrow(frame, (sx1, scy),  (zx1, scy),  SIGN_COL)
        _draw_arrow(frame, (sx2, scy),  (zx2, scy),  SIGN_COL)
        _draw_arrow(frame, (scx, sy1),  (scx, zy1),  SIGN_COL)
        _draw_arrow(frame, (scx, sy2),  (scx, zy2),  SIGN_COL)

        return frame


    # ─────────────────────────────────────
    # Main processing pipeline
    # ─────────────────────────────────────

    def process_frame(self, frame: np.ndarray) -> FrameResult:
        fps     = self._fps()
        results = self.model.predict(frame, conf=self.conf, imgsz=640, verbose=False)[0]

        buckets = self._parse(results)

        # ── Auto zone update (runs before person checks) ──────────────────────
        # In auto mode this re-evaluates the zone every frame.
        # In manual mode it's a fast no-op once the polygon is set.
        self._update_auto_zone(frame, buckets["cones"])
        # ─────────────────────────────────────────────────────────────────────

        persons = [self._check_person(p, buckets) for p in buckets["persons"]]

        alerts                  = []
        ts                      = time.strftime("%H:%M:%S")
        zone_intrusion_detected = False

        for p in persons:
            for v in p.violations:
                alerts.append(f"[{ts}] {v}")
            if p.in_zone:
                zone_intrusion_detected = True

        # Trigger voice ONLY for zone intrusions (respects cooldown internally)
        if self.voice_enabled and self.voice and zone_intrusion_detected:
            self.voice.trigger_zone_alert()

        annotated = self._draw_boxes(frame.copy(), buckets)
        annotated = self._draw_voice_indicator(annotated)

        return FrameResult(
            frame             = annotated,
            persons           = persons,
            alerts            = alerts,
            fps               = fps,
            violation_count   = sum(not p.is_compliant for p in persons),
            safe_count        = sum(p.is_compliant     for p in persons),
            zone_intrusion_count = sum(p.in_zone       for p in persons),
            zone_source       = self.zone_source,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Module-level drawing utilities
# (used by SafeSightDetector overlay methods — no class state needed)
# ─────────────────────────────────────────────────────────────────────────────

def _draw_dashed_line(
    frame: np.ndarray,
    pt1: tuple,
    pt2: tuple,
    color: tuple,
    thickness: int = 1,
    dash_len: int  = 8,
    gap_len: int   = 5,
) -> None:
    """Draw a dashed line between two points on frame (in-place)."""
    x1, y1 = pt1
    x2, y2 = pt2
    total  = np.hypot(x2 - x1, y2 - y1)
    if total < 1:
        return

    dx = (x2 - x1) / total
    dy = (y2 - y1) / total

    pos    = 0.0
    draw   = True
    seg    = dash_len

    while pos < total:
        end = min(pos + seg, total)
        if draw:
            ax = int(x1 + dx * pos)
            ay = int(y1 + dy * pos)
            bx = int(x1 + dx * end)
            by = int(y1 + dy * end)
            cv2.line(frame, (ax, ay), (bx, by), color, thickness)
        pos  += seg
        draw  = not draw
        seg   = gap_len if draw else dash_len


def _draw_dashed_rect(
    frame: np.ndarray,
    pt1: tuple,
    pt2: tuple,
    color: tuple,
    thickness: int = 1,
    dash_len: int  = 8,
    gap_len: int   = 5,
) -> None:
    """Draw a dashed rectangle (in-place)."""
    x1, y1 = pt1
    x2, y2 = pt2
    # Four sides: top, right, bottom (reversed), left (reversed)
    corners = [
        ((x1, y1), (x2, y1)),
        ((x2, y1), (x2, y2)),
        ((x2, y2), (x1, y2)),
        ((x1, y2), (x1, y1)),
    ]
    for a, b in corners:
        _draw_dashed_line(frame, a, b, color, thickness, dash_len, gap_len)


def _draw_arrow(
    frame: np.ndarray,
    pt1: tuple,
    pt2: tuple,
    color: tuple,
    thickness: int  = 1,
    tip_length: float = 0.25,
) -> None:
    """Draw a thin arrow from pt1 → pt2. Skips if points are identical."""
    if pt1 == pt2:
        return
    # Only draw if the arrow is long enough to be visible
    length = np.hypot(pt2[0] - pt1[0], pt2[1] - pt1[1])
    if length < 6:
        return
    cv2.arrowedLine(frame, pt1, pt2, color, thickness,
                    tipLength=tip_length, line_type=cv2.LINE_AA)