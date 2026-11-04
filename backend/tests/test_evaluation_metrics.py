from app.evaluation_metrics import box_iou, compare_boxes
from app.tracking import Detection


def person(x1, y1, x2, y2):
    return Detection((x1, y1, x2, y2), "person", 0.9)


def test_match_is_one_to_one_even_with_duplicate_predictions():
    truth = [(0.1, 0.1, 0.2, 0.5)]
    scores = compare_boxes([person(*truth[0]), person(*truth[0])], truth)
    assert (scores.true_positive, scores.false_positive, scores.missed) == (1, 1, 0)
    assert scores.precision == 0.5
    assert scores.recall == 1


def test_distinct_people_are_not_matched_to_one_person():
    predictions = [person(0.2, 0.2, 0.3, 0.6), person(0.4, 0.2, 0.5, 0.6)]
    scores = compare_boxes(predictions, [(0.2, 0.2, 0.3, 0.6)])
    assert scores.true_positive == 1
    assert scores.false_positive == 1
    assert scores.missed == 0


def test_missing_person_counts_as_missed():
    scores = compare_boxes([], [(0.1, 0.1, 0.3, 0.7)])
    assert (scores.true_positive, scores.false_positive, scores.missed) == (0, 0, 1)


def test_overlap_geometry():
    assert box_iou((0, 0, 1, 1), (0, 0, 1, 1)) == 1
    assert box_iou((0, 0, 0.2, 0.2), (0.8, 0.8, 1, 1)) == 0
