"""Adaptive, in-memory close-up scans for distant people in a fixed camera.

Full-frame detection always runs first. When affordable, two overlapping crops
provide a higher effective pixel density for small/partially visible people.
Only boxes from the current frame are admitted; this code never fabricates a
person from prior frames or identifies people by appearance.
"""

import math
import time
from dataclasses import dataclass

import numpy as np

from app.tracking import Detection


@dataclass(frozen=True)
class _Crop:
    x1: float
    y1: float
    x2: float
    y2: float


def _iou(a: Detection, b: Detection) -> float:
    ax1, ay1, ax2, ay2 = a.box
    bx1, by1, bx2, by2 = b.box
    intersection = max(0.0, min(ax2, bx2) - max(ax1, bx1)) * max(0.0, min(ay2, by2) - max(ay1, by1))
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - intersection
    return intersection / union if union > 0 else 0.0


def _same_person(a: Detection, b: Detection) -> bool:
    """Match geometrically consistent views, not merely overlapping people.

    Crop and full-frame detections of the same person may not have identical
    extents. A partial torso enclosed in a whole-person box is considered only
    when box size, center and footpoint are consistent. A broad overlap of two
    adjacent seated people must not cause them to be fused.
    """
    if a.label != b.label:
        return False
    overlap = _iou(a, b)
    if overlap >= 0.64:
        return True
    ax1, ay1, ax2, ay2 = a.box
    bx1, by1, bx2, by2 = b.box
    aw, ah, bw, bh = ax2 - ax1, ay2 - ay1, bx2 - bx1, by2 - by1
    if min(aw, ah, bw, bh) <= 0:
        return False
    if overlap >= 0.38:
        ratio = max(aw / bw, bw / aw, ah / bh, bh / ah)
        if ratio <= 1.45 and math.dist(a.anchor, b.anchor) < 0.025:
            return True
    # High containment can happen when one crop sees only a person's torso.
    # But never fuse a much smaller adjacent person inside a large error box.
    intersection = max(0.0, min(ax2, bx2) - max(ax1, bx1)) * max(0.0, min(ay2, by2) - max(ay1, by1))
    area_a, area_b = aw * ah, bw * bh
    area_ratio = min(area_a, area_b) / max(area_a, area_b)
    if area_ratio < 0.57 or intersection / min(area_a, area_b) < 0.89:
        return False
    if abs(a.anchor[0] - b.anchor[0]) > 0.14 * max(aw, bw):
        return False
    return abs(a.anchor[1] - b.anchor[1]) <= 0.16 * max(ah, bh)


def merge_people_with_counts(
    primary: list[Detection], closeups: list[Detection]
) -> tuple[list[Detection], int]:
    """Return distinct current-frame boxes and number of redundant proposals.

    A duplicate is not a track: nothing is carried forward from past frames.
    Diagnostic counts describe only geometry; they are not detection accuracy.
    """
    result: list[Detection] = []
    suppressed = 0
    # Full-frame detections take precedence over crop-local detections when
    # confidence is similar. Avoid allowing near-identical weak boxes to inflate
    # the owner-visible count. Sorting makes the result order deterministic.
    for candidate in [*primary, *sorted(closeups, key=lambda d: d.confidence, reverse=True)]:
        match = next(
            (i for i, existing in enumerate(result) if _same_person(existing, candidate)),
            None,
        )
        if match is None:
            if len(result) >= 96:
                continue
            result.append(candidate)
        else:
            suppressed += 1
            if candidate.confidence > result[match].confidence + 0.08:
                result[match] = candidate
    return result, suppressed


def merge_people(primary: list[Detection], closeups: list[Detection]) -> list[Detection]:
    """Suppress duplicates from overlapping crop/full-frame views."""
    merged, _ = merge_people_with_counts(primary, closeups)
    return merged


def _remap(
    detections: list[Detection], crop: _Crop, left_internal: bool, right_internal: bool
) -> list[Detection]:
    result = []
    for detection in detections:
        if detection.label != "person":
            continue
        x1, y1, x2, y2 = detection.box
        # Ignore truncated figures at the *internal* crop boundary. The
        # overlapping other crop can see them without cutting them in half.
        if (left_internal and x1 < 0.018) or (right_internal and x2 > 0.982):
            continue
        if not (0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1):
            continue
        mapped = (
            crop.x1 + x1 * (crop.x2 - crop.x1),
            crop.y1 + y1 * (crop.y2 - crop.y1),
            crop.x1 + x2 * (crop.x2 - crop.x1),
            crop.y1 + y2 * (crop.y2 - crop.y1),
        )
        if mapped[2] - mapped[0] < 0.004 or mapped[3] - mapped[1] < 0.012:
            continue
        result.append(Detection(mapped, "person", detection.confidence))
    return result


class PersonDetailScanner:
    """Scan both halves when fast enough; cool down if extra inference is slow.

    Uses the same loaded local YOLO model. No external requests, downloads,
    stored images, role recognition, or extra tracking identities.
    """

    def __init__(self, max_extra_seconds: float = 0.30, cooldown_frames: int = 20):
        self.max_extra_seconds = max_extra_seconds
        self.cooldown_frames = cooldown_frames
        self.reset()

    def reset(self) -> None:
        self.frame = 0
        self.pause_until = 0
        self.slow_streak = 0
        self.mode = "learning"
        self.added_candidates = 0
        self.closeup_passes = 0
        self.suppressed_duplicates = 0
        self.closeup_candidates = 0

    def augment(
        self, detector: object, frame: np.ndarray, primary: list[Detection], confidence: float
    ) -> list[Detection]:
        self.frame += 1
        self.added_candidates = 0
        self.closeup_passes = 0
        self.suppressed_duplicates = 0
        self.closeup_candidates = 0
        if self.frame < self.pause_until:
            self.mode = "performance_limited"
            return primary
        height, width = frame.shape[:2]
        if height < 160 or width < 320:
            self.mode = "unavailable"
            return primary
        crop_rects = (_Crop(0, 0, 0.59, 1), _Crop(0.41, 0, 1, 1))
        closeups: list[Detection] = []
        started = time.perf_counter()
        try:
            for crop in crop_rects:
                x1 = int(crop.x1 * width)
                x2 = int(crop.x2 * width)
                # Detector is always the already-initialized local YoloDetector.
                scan = detector.detect(  # type: ignore[attr-defined]
                    np.ascontiguousarray(frame[:, x1:x2]), confidence
                )
                self.closeup_passes += 1
                closeups.extend(_remap(scan, crop, left_internal=x1 > 0, right_internal=x2 < width))
        except (RuntimeError, ValueError):
            # A secondary scan must never take down the primary camera AI.
            self.pause_until = self.frame + self.cooldown_frames
            self.mode = "performance_limited"
            return primary
        elapsed = time.perf_counter() - started
        self.slow_streak = self.slow_streak + 1 if elapsed > self.max_extra_seconds else 0
        if self.slow_streak >= 2:
            self.pause_until = self.frame + self.cooldown_frames
            self.slow_streak = 0
        self.closeup_candidates = len(closeups)
        merged, self.suppressed_duplicates = merge_people_with_counts(primary, closeups)
        self.added_candidates = max(0, len(merged) - len(primary))
        self.mode = "scanning"
        return merged
