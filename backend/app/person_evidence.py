"""Short-lived, anonymous confirmation of weak person detections.

The detector occasionally produces a weak candidate for a distant or partially
occluded person. Require a second *current* model observation before admitting
that candidate to current counts. No boxes are invented by this module.
"""

from dataclasses import dataclass

from app.tracking import Detection


def _overlap(a: Detection, b: Detection) -> float:
    ax1, ay1, ax2, ay2 = a.box
    bx1, by1, bx2, by2 = b.box
    intersection = max(0.0, min(ax2, bx2) - max(ax1, bx1)) * max(0.0, min(ay2, by2) - max(ay1, by1))
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - intersection
    return intersection / union if union > 0 else 0.0


@dataclass
class _Candidate:
    detection: Detection
    seen: float
    hits: int
    admitted: bool


class PersonEvidenceGate:
    """Admit strong detections immediately and short-lived weak matches twice.

    Candidate memory is bounded, in RAM, and discarded at source changes, camera
    movement, or the end of monitoring. This is evidence checking, not identity
    recognition, person re-identification, or temporal interpolation.
    """

    def __init__(self, max_gap: float = 1.4, capacity: int = 96):
        self.max_gap = max_gap
        self.capacity = capacity
        self.reset()

    def reset(self) -> None:
        self.candidates: list[_Candidate] = []
        self.weak_admitted = 0

    @staticmethod
    def candidate_floor(configured_confidence: float) -> float:
        return min(configured_confidence, max(0.18, configured_confidence - 0.12))

    def filter(
        self, detections: list[Detection], now: float, configured_confidence: float
    ) -> list[Detection]:
        recent = [item for item in self.candidates if 0 <= now - item.seen <= self.max_gap]
        pairs: list[tuple[float, int, int]] = []
        for i, prior_candidate in enumerate(recent):
            for j, detection in enumerate(detections):
                if detection.label != prior_candidate.detection.label:
                    continue
                # Require similar image-plane location and overlapping boxes;
                # nearby separate people must not confirm one another.
                dx = abs(detection.anchor[0] - prior_candidate.detection.anchor[0])
                dy = abs(detection.anchor[1] - prior_candidate.detection.anchor[1])
                iou = _overlap(detection, prior_candidate.detection)
                min_overlap = 0.45 if now - prior_candidate.seen > 0.8 else 0.12
                if dx <= 0.075 and dy <= 0.11 and iou >= min_overlap:
                    pairs.append((1 - iou + dx + dy, i, j))
        matches: dict[int, _Candidate] = {}
        used_previous: set[int] = set()
        for _, prior_index, current in sorted(pairs):
            if prior_index not in used_previous and current not in matches:
                matches[current] = recent[prior_index]
                used_previous.add(prior_index)
        updated: list[_Candidate] = []
        accepted: list[Detection] = []
        weak_admitted = 0
        for index, detection in enumerate(detections[: self.capacity]):
            matched_candidate = matches.get(index)
            # Only consecutive observations of a weak candidate count as
            # confirmation. A single weak box cannot create a reported person.
            hits = min(matched_candidate.hits + 1, 100) if matched_candidate else 1
            strong = detection.confidence >= configured_confidence
            admitted = strong or bool(matched_candidate and matched_candidate.admitted) or hits >= 2
            updated.append(_Candidate(detection, now, hits, admitted))
            if admitted:
                accepted.append(detection)
                if not strong:
                    weak_admitted += 1
        # Preserve only previously admitted evidence across one missed sample.
        # A missing frame still returns no person and contributes zero to counts;
        # this merely avoids treating a genuine weak re-detection as a stranger.
        matched_ids = {id(item) for item in matches.values()}
        recovering = [item for item in recent if item.admitted and id(item) not in matched_ids]
        self.candidates = (updated + recovering)[: self.capacity]
        self.weak_admitted = weak_admitted
        return accepted
