import cv2
import numpy as np
from ultralytics import YOLO
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class _Det:
    """Lightweight detection used internally by ZoneDetector."""

    bbox: Tuple[int, int, int, int]
    label: str
    confidence: float

    @property
    def center(self) -> Tuple[int, int]:
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) // 2, (y1 + y2) // 2)


class ZoneDetector:

    DANGER_SIGN_CLASSES = {
        # Generic / common names
        "danger",
        "dangerous",
        "restricted",
        "restricted area",
        "no entry",
        "caution",
        "warning",
        "keep out",
        "authorized personnel only",
        "hazard",
        "do not enter",
        "sign",
        "danger sign",
        "warning sign",
        "safety sign",
        # Actual sign_best.pt class names (lowercase for matching)
        "explosives",
        "flammable",
        "flammable gases",
        "flammable liquid",
        "corrosive",
        "radioactive",
        "poisons",
        "toxic gases",
        "oxidizing substances",
        "hazardous voltage",
        "miscellaneous dangerous goods",
    }

    def __init__(
        self,
        sign_model_path: str,
        sign_conf: float = 0.40,
        sign_expand_x: float = 2.5,
        sign_expand_y: float = 2.5,
        min_cones: int = 3,
        cone_padding: int = 30,
        prefer_cones: bool = True,
    ):
        print(f"🔍 Loading sign detection model: {sign_model_path}")
        self.sign_model = YOLO(sign_model_path)
        self.sign_conf = sign_conf
        self.sign_expand_x = sign_expand_x
        self.sign_expand_y = sign_expand_y
        self.min_cones = min_cones
        self.cone_padding = cone_padding
        self.prefer_cones = prefer_cones

        self._sign_classes_lower = {c.lower() for c in self.DANGER_SIGN_CLASSES}

        print(f"✅ Sign model loaded | classes: {list(self.sign_model.names.values())}")

    def detect(
        self,
        frame: np.ndarray,
        cone_detections: list,
    ) -> Tuple[Optional[np.ndarray], str]:
        """
        Returns (polygon, source) where:
          polygon  — np.ndarray of shape (N, 1, 2), dtype int32,
                     or None if no zone was inferred.
          source   — one of "AUTO:CONES", "AUTO:SIGN", "NONE"
        """
        cone_polygon = self._cone_hull(cone_detections)
        sign_polygon, sign_det = self._sign_zone_with_det(frame)

        if self.prefer_cones:
            if cone_polygon is not None:
                self._last_detected_sign = None
                return cone_polygon, "AUTO:CONES"
            if sign_polygon is not None:
                self._last_detected_sign = sign_det
                return sign_polygon, "AUTO:SIGN"
        else:
            if sign_polygon is not None:
                self._last_detected_sign = sign_det
                return sign_polygon, "AUTO:SIGN"
            if cone_polygon is not None:
                self._last_detected_sign = None
                return cone_polygon, "AUTO:CONES"

        self._last_detected_sign = None
        return None, "NONE"

    def _cone_hull(self, cones: list) -> Optional[np.ndarray]:
        """
        Builds a convex hull polygon around cone bounding-box centers.
        Requires at least self.min_cones detections.

        cones: list of Detection (or any object with .center attr)
        """
        if len(cones) < self.min_cones:
            return None

        centers = np.array([c.center for c in cones], dtype=np.float32)

        if self.cone_padding > 0:
            padded = []
            for cx, cy in centers:
                for dx in [-self.cone_padding, self.cone_padding]:
                    for dy in [-self.cone_padding, self.cone_padding]:
                        padded.append([cx + dx, cy + dy])
            centers = np.array(padded, dtype=np.float32)

        hull = cv2.convexHull(centers)
        return hull.astype(np.int32)

    def _sign_zone(self, frame: np.ndarray) -> Optional[np.ndarray]:
        polygon, _ = self._sign_zone_with_det(frame)
        return polygon

    def _sign_zone_with_det(self, frame: np.ndarray):
        best = self._find_best_sign(frame)
        if best is None:
            return None, None
        h, w = frame.shape[:2]
        return self._expand_bbox_to_polygon(best.bbox, w, h), best

    def _find_best_sign(self, frame: np.ndarray) -> Optional[_Det]:
        if self.sign_model is None:
            return None

        results = self.sign_model.predict(
            frame,
            conf=self.sign_conf,
            imgsz=640,
            verbose=False,
        )[0]

        best: Optional[_Det] = None

        for box in results.boxes:
            label = self.sign_model.names[int(box.cls[0])].lower()
            conf = float(box.conf[0])

            is_danger = (
                len(self.sign_model.names) <= 50  # dedicated model → trust all
                or label in self._sign_classes_lower  # large general model → filter
            )
            if not is_danger:
                continue

            x1, y1, x2, y2 = map(int, box.xyxy[0])
            det = _Det((x1, y1, x2, y2), label, conf)

            if best is None or conf > best.confidence:
                best = det

        return best

    def _expand_bbox_to_polygon(
        self,
        bbox: Tuple[int, int, int, int],
        frame_w: int,
        frame_h: int,
    ) -> np.ndarray:

        x1, y1, x2, y2 = bbox
        bw = x2 - x1
        bh = y2 - y1
        cx = (x1 + x2) / 2
        cy = (y1 + y2) / 2

        half_w = (bw / 2) * self.sign_expand_x
        half_h = (bh / 2) * self.sign_expand_y

        nx1 = int(max(0, cx - half_w))
        ny1 = int(max(0, cy - half_h))
        nx2 = int(min(frame_w, cx + half_w))
        ny2 = int(min(frame_h, cy + half_h))

        polygon = np.array(
            [
                [nx1, ny1],
                [nx2, ny1],
                [nx2, ny2],
                [nx1, ny2],
            ],
            dtype=np.int32,
        )

        return polygon

    def annotate_debug(
        self,
        frame: np.ndarray,
        polygon: Optional[np.ndarray],
        source: str,
    ) -> np.ndarray:
        """
        Draws the auto-detected zone + source label on a copy of the frame.
        Call this only in debug/testing; production drawing is in detector.py.
        """
        out = frame.copy()
        if polygon is not None:
            cv2.polylines(out, [polygon], True, (0, 255, 128), 2)
            cx = (
                int(polygon[:, 0].mean())
                if polygon.ndim == 2
                else int(polygon[:, 0, 0].mean())
            )
            cy = (
                int(polygon[:, 1].mean())
                if polygon.ndim == 2
                else int(polygon[:, 0, 1].mean())
            )
            cv2.putText(
                out,
                f"[{source}]",
                (cx - 50, cy),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 128),
                2,
            )
        return out

