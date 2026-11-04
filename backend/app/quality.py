"""Deterministic temporal continuity checks, independent of decoder or detector packages."""

from dataclasses import dataclass


@dataclass
class Continuity:
    previous_hash: bytes | None = None
    identical_since: float | None = None
    previous_capture: float | None = None
    previous_epoch: int = 0

    def update(
        self, digest: bytes, captured: float, frame_change: float, epoch: int, target_fps: float
    ) -> list[str]:
        if digest != self.previous_hash or self.identical_since is None:
            self.identical_since = captured
        flags = []
        if captured - self.identical_since >= 3:
            flags.append("frozen_input")
        if self.previous_capture is not None:
            if frame_change > 0.30:
                flags.append("camera_movement")
            if captured - self.previous_capture > max(3, 3 / target_fps):
                flags.append("frame_gap")
        if self.previous_capture is not None and epoch != self.previous_epoch:
            flags.append("source_boundary")
        self.previous_hash = digest
        self.previous_capture = captured
        self.previous_epoch = epoch
        return flags


class ViewStability:
    """Conservative camera-view shift guard, based on background optical flow.

    This is NOT video stabilization. Camera pans or substantial repositioning
    invalidate scene hotspots and crossing/shift comparisons.
    """

    def __init__(self) -> None:
        self.previous = None
        self.unstable_until = 0.0

    def update(self, image, at: float) -> bool:
        import cv2
        import numpy as np

        gray = cv2.cvtColor(cv2.resize(image, (320, 180)), cv2.COLOR_BGR2GRAY)
        previous = self.previous
        self.previous = gray
        if previous is None:
            return False
        points = cv2.goodFeaturesToTrack(
            previous, maxCorners=140, qualityLevel=0.035, minDistance=12, blockSize=7
        )
        if points is not None and len(points) >= 15:
            next_points, mask, _ = cv2.calcOpticalFlowPyrLK(previous, gray, points, None)
            if next_points is not None and mask is not None:
                valid = mask.reshape(-1) == 1
                if int(valid.sum()) >= 12:
                    shifts = next_points[valid] - points[valid]
                    dx, dy = np.median(shifts.reshape(-1, 2), axis=0)
                    distances = np.linalg.norm(shifts.reshape(-1, 2), axis=1)
                    # Requires a coherent global translation rather than a
                    # handful of moving people. Scale is 320 x 180 pixels.
                    coherent = np.mean(np.abs(distances - np.hypot(dx, dy)) < 5)
                    if np.hypot(dx, dy) >= 7.5 and coherent >= 0.55:
                        self.unstable_until = at + 3.0
        return at < self.unstable_until
