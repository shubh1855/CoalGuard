from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import cv2
import time
from deep_sort_realtime.deepsort_tracker import DeepSort

from .detector import FrameResult, PersonStatus, SafeSightDetector
from .violation_logger import ViolationEvent, ViolationLogger


@dataclass
class TrackedPersonStatus:
    worker_id: int
    status: PersonStatus
    track_bbox: Tuple[int, int, int, int]

    @property
    def violations(self) -> List[str]:
        return self.status.violations

    @property
    def person(self):
        return self.status.person

    @property
    def is_compliant(self) -> bool:
        return self.status.is_compliant


@dataclass
class TrackedFrameResult:
    frame: object
    persons: List[PersonStatus]
    tracked_persons: List[TrackedPersonStatus]
    alerts: List[str]
    fps: float
    violation_count: int
    safe_count: int
    zone_intrusion_count: int
    violation_events: List[ViolationEvent]
    zone_source: str = "NONE"          # ← NEW: forwarded from SafeSightDetector

    @property
    def total_workers(self) -> int:
        return len(self.tracked_persons)


class TrackedSafeSightDetector:
    def __init__(
        self,
        model_path: str,
        conf_threshold: float = 0.35,
        source_type: str = "demo_feed",
        session_epoch: int | None = None,
        enable_voice: bool = True,
        sign_model_path: Optional[str] = None,   # ← NEW
        zone_mode: str = "auto",                 # ← NEW
    ) -> None:
        normalized_source = source_type.lower().replace(" ", "_")
        self.detector = SafeSightDetector(
            model_path,
            conf_threshold=conf_threshold,
            enable_voice=enable_voice,
            sign_model_path=sign_model_path,     # ← forwarded
            zone_mode=zone_mode,                 # ← forwarded
        )
        self.tracker = DeepSort(max_age=30, n_init=1, max_iou_distance=0.7)
        self.logger = ViolationLogger(
            source_type=normalized_source,
            session_epoch=session_epoch,
        )
        self.active_violations: set[tuple[int, str]] = set()
        self.last_seen_violations: set[tuple[int, str]] = set()

    # ── Zone proxies ──────────────────────────────────────────────────────────

    def set_zone(self, points: List[Tuple[int, int]], source: str = "MANUAL") -> None:
        self.detector.set_zone(points, source=source)

    def clear_zone(self) -> None:
        self.detector.clear_zone()

    def set_zone_mode(self, mode: str) -> None:           # ← NEW proxy
        self.detector.set_zone_mode(mode)

    @property
    def zone_polygon(self):
        return self.detector.zone_polygon

    @zone_polygon.setter
    def zone_polygon(self, value) -> None:
        self.detector.zone_polygon = value

    @property
    def zone_source(self) -> str:                         # ← NEW proxy
        return self.detector.zone_source

    # ── Voice proxies ─────────────────────────────────────────────────────────

    @property
    def voice(self):
        return self.detector.voice

    @property
    def voice_enabled(self) -> bool:
        return self.detector.voice_enabled

    @voice_enabled.setter
    def voice_enabled(self, value: bool) -> None:
        self.detector.voice_enabled = value

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _iou(
        self,
        b1: Tuple[int, int, int, int],
        b2: Tuple[int, int, int, int],
    ) -> float:
        return self.detector._iou(b1, b2)

    def _track_people(self, frame_result: FrameResult, frame) -> List[TrackedPersonStatus]:
        detections = []
        for person_status in frame_result.persons:
            x1, y1, x2, y2 = person_status.person.bbox
            detections.append(
                (
                    [x1, y1, x2 - x1, y2 - y1],
                    person_status.person.confidence,
                    "person",
                )
            )

        if not detections:
            return []

        tracks = self.tracker.update_tracks(detections, frame=frame)
        available_people: Dict[int, PersonStatus] = {
            index: status for index, status in enumerate(frame_result.persons)
        }
        tracked_people: List[TrackedPersonStatus] = []

        for track in tracks:
            if not track.is_confirmed():
                continue

            track_bbox = tuple(map(int, track.to_ltrb()))
            best_match_index = None
            best_iou = 0.0

            for index, status in available_people.items():
                overlap = self._iou(track_bbox, status.person.bbox)
                if overlap > best_iou:
                    best_iou = overlap
                    best_match_index = index

            if best_match_index is None or best_iou <= 0:
                continue

            matched_status = available_people.pop(best_match_index)
            tracked_people.append(
                TrackedPersonStatus(
                    worker_id=int(track.track_id),
                    status=matched_status,
                    track_bbox=track_bbox,
                )
            )

        return tracked_people

    def _draw_worker_ids(self, frame, tracked_people: List[TrackedPersonStatus]) -> None:
        for tracked in tracked_people:
            x1, y1, _, _ = tracked.track_bbox
            cv2.putText(
                frame,
                f"Worker {tracked.worker_id}",
                (x1, max(y1 - 20, 20)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2,
            )

    def _build_alerts(self, tracked_people: List[TrackedPersonStatus]) -> List[str]:
        alerts: List[str] = []
        for tracked in tracked_people:
            for violation in tracked.violations:
                alerts.append(f"Worker {tracked.worker_id}: {violation}")
        return alerts

    def _log_new_violations(
        self,
        frame,
        tracked_people: List[TrackedPersonStatus],
    ) -> List[ViolationEvent]:
        current_active: set[tuple[int, str]] = set()
        events: List[ViolationEvent] = []
        event_epoch = int(time.time())

        for tracked in tracked_people:
            for violation in tracked.violations:
                key = (tracked.worker_id, violation)
                current_active.add(key)
                if key not in self.last_seen_violations:
                    event = self.logger.log_violation(
                        worker_id=tracked.worker_id,
                        violation_type=violation,
                        frame=frame,
                        timestamp_epoch=event_epoch,
                    )
                    if event is not None:
                        events.append(event)

        self.active_violations = current_active
        self.last_seen_violations = current_active
        return events

    def process_frame(self, frame) -> TrackedFrameResult:
        frame_result = self.detector.process_frame(frame)
        tracked_people = self._track_people(frame_result, frame)

        annotated_frame = frame_result.frame.copy()
        self._draw_worker_ids(annotated_frame, tracked_people)
        events = self._log_new_violations(annotated_frame, tracked_people)

        return TrackedFrameResult(
            frame=annotated_frame,
            persons=frame_result.persons,
            tracked_persons=tracked_people,
            alerts=self._build_alerts(tracked_people),
            fps=frame_result.fps,
            violation_count=sum(
                not tracked.is_compliant for tracked in tracked_people
            ),
            safe_count=sum(tracked.is_compliant for tracked in tracked_people),
            zone_intrusion_count=sum(
                "ZONE INTRUSION" in tracked.violations for tracked in tracked_people
            ),
            violation_events=events,
            zone_source=frame_result.zone_source,   # ← forwarded from SafeSightDetector
        )
