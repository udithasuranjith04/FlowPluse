"""Focused scans: no double counting, no inferred people, bounded CPU use."""

import numpy as np

from app.person_detail import PersonDetailScanner, merge_people
from app.tracking import Detection


def person(x1: float, y1: float, x2: float, y2: float, confidence=0.75):
    return Detection((x1, y1, x2, y2), "person", confidence)


def test_closeup_recovery_reprojects_boxes_without_moving_the_camera():
    frame = np.zeros((360, 1280, 3), dtype=np.uint8)

    class FakeDetector:
        def __init__(self):
            self.calls = 0

        def detect(self, crop, threshold):
            self.calls += 1
            assert crop.shape[0] == 360 and threshold == 0.23
            if self.calls == 1:
                return [person(0.25, 0.20, 0.34, 0.56)]
            return [person(0.48, 0.2, 0.60, 0.62)]

    detector = FakeDetector()
    scanner = PersonDetailScanner()
    recovered = scanner.augment(detector, frame, [], 0.23)
    assert len(recovered) == 2
    assert abs(recovered[0].box[0] - 0.1475) < 0.0001
    assert abs(recovered[1].box[0] - (0.41 + 0.48 * 0.59)) < 0.0001
    assert scanner.closeup_passes == 2
    assert scanner.added_candidates == 2


def test_same_person_from_full_frame_and_two_closeups_is_not_counted_three_times():
    original = person(0.46, 0.25, 0.51, 0.62, 0.65)
    crop_a = person(0.459, 0.247, 0.512, 0.619, 0.74)
    crop_b = person(0.462, 0.250, 0.510, 0.620, 0.70)
    merged = merge_people([original], [crop_a, crop_b])
    assert len(merged) == 1
    assert merged[0].confidence == 0.74


def test_two_partly_overlapping_people_are_not_fused_into_one():
    first = person(0.42, 0.27, 0.51, 0.68)
    second = person(0.465, 0.28, 0.555, 0.68)
    assert len(merge_people([first], [second])) == 2


def test_internal_crop_boundary_does_not_create_cut_off_duplicate():
    frame = np.zeros((360, 1280, 3), dtype=np.uint8)

    class FakeDetector:
        def __init__(self):
            self.calls = 0

        def detect(self, crop, threshold):
            self.calls += 1
            return [person(0.92, 0.1, 0.997, 0.4)] if self.calls == 1 else []

    scanner = PersonDetailScanner()
    assert scanner.augment(FakeDetector(), frame, [], 0.23) == []
    assert scanner.added_candidates == 0


def test_slow_extra_scans_auto_pause_then_retry_without_losing_full_frame():
    frame = np.zeros((360, 640, 3), dtype=np.uint8)

    class FakeDetector:
        def detect(self, crop, threshold):
            return []

    scanner = PersonDetailScanner(max_extra_seconds=-1, cooldown_frames=4)
    base = [person(0.1, 0.2, 0.3, 0.7)]
    assert scanner.augment(FakeDetector(), frame, base, 0.23) == base
    assert scanner.augment(FakeDetector(), frame, base, 0.23) == base
    assert scanner.augment(FakeDetector(), frame, base, 0.23) == base
    assert scanner.mode == "performance_limited"
    assert scanner.closeup_passes == 0
    assert scanner.augment(FakeDetector(), frame, base, 0.23) == base
    assert scanner.augment(FakeDetector(), frame, base, 0.23) == base
    assert scanner.augment(FakeDetector(), frame, base, 0.23) == base
    assert scanner.closeup_passes == 2


def test_secondary_detector_failure_never_disables_primary_detection():
    frame = np.zeros((360, 640, 3), dtype=np.uint8)

    class FailingDetector:
        def detect(self, crop, threshold):
            raise RuntimeError("secondary pass unavailable")

    scanner = PersonDetailScanner()
    base = [person(0.1, 0.2, 0.3, 0.7)]
    assert scanner.augment(FailingDetector(), frame, base, 0.23) == base
    assert scanner.mode == "performance_limited"


def test_closeup_merges_similar_partial_box_from_same_person():
    from app.person_detail import merge_people_with_counts

    full = person(0.30, 0.20, 0.46, 0.70, 0.70)
    partial = person(0.315, 0.24, 0.445, 0.67, 0.81)
    merged, duplicates = merge_people_with_counts([full], [partial])
    assert len(merged) == 1
    assert duplicates == 1


def test_multiple_distinct_seated_people_remain_distinct_despite_overlap():
    from app.person_detail import merge_people_with_counts

    left = person(0.36, 0.30, 0.52, 0.72, 0.85)
    right = person(0.45, 0.32, 0.61, 0.74, 0.82)
    merged, duplicates = merge_people_with_counts([left], [right])
    assert len(merged) == 2
    assert duplicates == 0


def test_suppression_counts_are_per_frame_only():
    frame = np.zeros((360, 1280, 3), dtype=np.uint8)

    class RepeatingDetector:
        def detect(self, crop, threshold):
            return [person(0.20, 0.12, 0.28, 0.56)]

    scanner = PersonDetailScanner()
    scanner.augment(RepeatingDetector(), frame, [], 0.23)
    assert scanner.closeup_candidates == 2
    assert scanner.added_candidates >= 1
    scanner.reset()
    assert scanner.suppressed_duplicates == 0
    assert scanner.closeup_candidates == 0
