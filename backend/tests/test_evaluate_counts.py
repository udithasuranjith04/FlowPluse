"""Evaluate manually verified count data without needing video or a model."""

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "evaluate_counts.py"
spec = importlib.util.spec_from_file_location("flowpulse_count_eval", SCRIPT)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def row(frame: str, reference: str, detected: str) -> dict[str, str]:
    return {"frame_id": frame, "reference_people": reference, "detected_people": detected}


def test_count_evaluation_reports_error_and_exact_fraction():
    result = module.evaluate([row("a", "3", "3"), row("b", "2", "4"), row("c", "1", "0")])
    assert result == {
        "frames": 3,
        "mae_people": 1.0,
        "rmse_people": 1.291,
        "mean_error_people": 0.3333,
        "exact_count_fraction": 0.3333,
        "within_one_person_fraction": 0.6667,
    }


@pytest.mark.parametrize(
    "data",
    [
        [],
        [row("a", "0", "-1")],
        [row("a", "wrong", "1")],
        [row("a", "1.5", "1")],
        [row("a", "1", "1"), row("a", "2", "2")],
        [row("", "1", "1")],
    ],
)
def test_invalid_evaluation_data_rejected(data):
    with pytest.raises(ValueError):
        module.evaluate(data)
