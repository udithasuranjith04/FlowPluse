import time
from pathlib import Path

import cv2
import numpy as np

from app.tracking import Track


class EvidenceStore:
    """Fail-closed, source-pixel-free evidence: a schematic, not a camera photograph."""

    def __init__(self, directory: Path, enabled: bool, ttl_hours: float):
        self.directory, self.enabled, self.ttl_seconds = directory, enabled, ttl_hours * 3600
        self.last_error: str | None = None

    def save(self, event_id: str, tracks: list[Track]) -> str | None:
        if not self.enabled:
            return None
        try:
            # Never pass a raw frame into the retention boundary.
            canvas = np.full((270, 480, 3), (25, 31, 38), dtype=np.uint8)
            cv2.putText(
                canvas,
                "REDACTED SCHEMATIC - NO SOURCE PIXELS",
                (12, 22),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.34,
                (200, 210, 220),
                1,
            )
            for track in tracks:
                x1, y1, x2, y2 = track.detection.box
                cv2.rectangle(
                    canvas,
                    (int(x1 * 480), int(y1 * 270)),
                    (int(x2 * 480), int(y2 * 270)),
                    (190, 180, 70),
                    2,
                )
            success, buffer = cv2.imencode(".jpg", canvas)
            if not success:
                return None
            self.directory.mkdir(parents=True, exist_ok=True)
            (self.directory / f"{event_id}.jpg").write_bytes(buffer.tobytes())
            return f"/api/events/{event_id}/evidence"
        except (OSError, cv2.error, ValueError):
            return None

    def purge(self) -> None:
        self.last_error = None
        if self.directory.is_dir():
            for file in self.directory.glob("*.jpg"):
                try:
                    if time.time() - file.stat().st_mtime > self.ttl_seconds:
                        file.unlink(missing_ok=True)
                except FileNotFoundError:
                    continue  # Another cleanup request already removed the file.
                except OSError:
                    self.last_error = (
                        "Evidence cleanup failed. Check runtime directory permissions."
                    )

    def get(self, event_id: str) -> Path | None:
        if not self.enabled:
            return None
        self.purge()
        path = self.directory / f"{event_id}.jpg"
        try:
            if path.is_file() and time.time() - path.stat().st_mtime <= self.ttl_seconds:
                return path
        except OSError:
            pass
        return None
