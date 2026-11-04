"""Offline per-frame bounding-box comparison against operator-created labels.

No identities, appearance data, footage, or annotations are transmitted or
persisted by this helper. Spatial IoU is used only to assess boxes in a frame.
"""

from dataclasses import dataclass

from app.tracking import Detection


@dataclass(frozen=True)
class BoxScores:
    true_positive: int
    false_positive: int
    missed: int

    @property
    def precision(self) -> float:
        total = self.true_positive + self.false_positive
        return self.true_positive / total if total else 0.0

    @property
    def recall(self) -> float:
        total = self.true_positive + self.missed
        return self.true_positive / total if total else 0.0


def box_iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    intersection = max(0, min(ax2, bx2) - max(ax1, bx1)) * max(0, min(ay2, by2) - max(ay1, by1))
    union = max(0, (ax2 - ax1) * (ay2 - ay1)) + max(0, (bx2 - bx1) * (by2 - by1)) - intersection
    return intersection / union if union > 0 else 0.0


def compare_boxes(
    detections: list[Detection],
    references: list[tuple[float, float, float, float]],
    minimum_iou: float = 0.5,
) -> BoxScores:
    """Count one-to-one matches; duplicate predictions remain false positives."""
    if not 0 < minimum_iou <= 1:
        raise ValueError("IoU threshold must be between zero and one")
    proposals = sorted(
        (
            (box_iou(detection.box, box), i, j)
            for i, detection in enumerate(detections)
            for j, box in enumerate(references)
        ),
        reverse=True,
    )
    used_predictions: set[int] = set()
    used_references: set[int] = set()
    for overlap, i, j in proposals:
        if overlap < minimum_iou:
            break
        if i in used_predictions or j in used_references:
            continue
        used_predictions.add(i)
        used_references.add(j)
    return BoxScores(
        len(used_predictions),
        len(detections) - len(used_predictions),
        len(references) - len(used_references),
    )
