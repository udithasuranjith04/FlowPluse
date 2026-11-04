import pytest
from scripts.compare_person_models import annotation_metrics, read_boxes

from app.tracking import Detection


def test_csv_box_annotations_support_multiple_people_at_same_time(tmp_path):
    path = tmp_path / "reference.csv"
    path.write_text("seconds,x1,y1,x2,y2\n1.0,0.1,0.1,0.2,0.4\n1.0,0.3,0.1,0.4,0.4\n")
    truth = read_boxes(path)
    assert len(truth) == 1 and len(truth[1.0]) == 2
    predicted = [[Detection(truth[1.0][0], "person", 0.8)]]
    scores = annotation_metrics(predicted, [truth[1.0]])
    assert scores["tp"] == 1 and scores["missed"] == 1
    assert scores["precision"] == 1.0 and scores["recall"] == 0.5


def test_invalid_boxes_are_rejected_without_loading_camera(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("seconds,x1,y1,x2,y2\n1,0.6,0.2,0.4,0.5\n")
    with pytest.raises(ValueError):
        read_boxes(path)


@pytest.mark.parametrize("value", ["nan", "inf", "-inf"])
def test_nonfinite_annotation_values_are_rejected(tmp_path, value):
    path = tmp_path / "bad.csv"
    path.write_text(f"seconds,x1,y1,x2,y2\n1,{value},0.2,0.4,0.5\n")
    with pytest.raises(ValueError):
        read_boxes(path)


def test_no_predictions_reports_missed_box():
    scores = annotation_metrics([[]], [[(0.1, 0.1, 0.2, 0.4)]])
    assert scores == {
        "precision": 0.0,
        "recall": 0.0,
        "f1": 0.0,
        "tp": 0,
        "fp": 0,
        "missed": 1,
    }
