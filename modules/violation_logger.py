from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
import time


@dataclass
class ViolationEvent:
    timestamp_epoch: int
    worker_id: int
    violation_type: str
    image_path: str
    source_type: str


class ViolationLogger:
    def __init__(
        self,
        source_type: str,
        session_epoch: int | None = None,
        base_dir: Path | None = None,
        capture_cooldown_seconds: int = 5,
    ) -> None:
        self.source_type = source_type
        self.session_epoch = session_epoch or int(time.time())
        self.base_dir = (base_dir or Path(__file__).resolve().parent).resolve()
        self.data_dir = self.base_dir / "data"
        self.evidence_dir = self.base_dir / "evidence" / str(self.session_epoch)
        self.csv_path = self.data_dir / f"violations_{self.session_epoch}.csv"
        self.capture_cooldown_seconds = capture_cooldown_seconds
        self._last_capture_at: dict[tuple[int, str], int] = {}

        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_csv_header()

    def _ensure_csv_header(self) -> None:
        if self.csv_path.exists():
            return

        with self.csv_path.open("w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(
                [
                    "timestamp_epoch",
                    "worker_id",
                    "violation_type",
                    "image_path",
                    "source_type",
                ]
            )

    def log_violation(
        self,
        worker_id: int,
        violation_type: str,
        frame,  # np.ndarray — lazy import avoids requiring numpy at module load
        timestamp_epoch: int | None = None,
    ) -> ViolationEvent | None:
        event_epoch = timestamp_epoch or int(time.time())
        violation_key = (worker_id, violation_type)
        last_capture_at = self._last_capture_at.get(violation_key)

        if (
            last_capture_at is not None
            and event_epoch - last_capture_at < self.capture_cooldown_seconds
        ):
            return None

        safe_violation = violation_type.lower().replace(" ", "_")
        filename = f"worker_{worker_id}_{safe_violation}_{event_epoch}.jpg"
        image_path = self.evidence_dir / filename

        import cv2  # lazy import — only needed when actually writing evidence frames
        cv2.imwrite(str(image_path), frame)
        self._last_capture_at[violation_key] = event_epoch

        event = ViolationEvent(
            timestamp_epoch=event_epoch,
            worker_id=worker_id,
            violation_type=violation_type,
            image_path=str(image_path.relative_to(self.base_dir)),
            source_type=self.source_type,
        )

        with self.csv_path.open("a", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(
                [
                    event.timestamp_epoch,
                    event.worker_id,
                    event.violation_type,
                    event.image_path,
                    event.source_type,
                ]
            )

        return event


def log_violation_to_db(db_session, site_id, worker_id, violation_type, image_path=None):
    """Write a CV violation and alert to the CoalGuard database."""
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
    from database import Violation, AlertLog
    v = Violation(
        site_id=site_id,
        worker_id=str(worker_id),
        violation_type=violation_type,
        source="CV",
        image_path=image_path,
    )
    db_session.add(v)
    a = AlertLog(
        site_id=site_id,
        alert_type="CV Violation",
        message=f"{worker_id} -- {violation_type}",
        severity="High",
        channel="Dashboard",
    )
    db_session.add(a)
    db_session.commit()
