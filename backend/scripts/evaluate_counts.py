"""Offline evaluation of *visible-person count* errors against manually checked CSV.

Does not open video, access a camera, identify people, or claim tracking accuracy.
Examples and usage: docs/RELEASE_CHECKLIST.md
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path


def evaluate(rows: list[dict[str, str]]) -> dict[str, float | int]:
    """Compute objective, explicitly scoped whole-frame count metrics."""
    if not rows:
        raise ValueError("No annotated frames found")
    differences: list[int] = []
    identifiers: set[str] = set()
    for line, row in enumerate(rows, start=2):
        identity = (row.get("frame_id") or "").strip()
        if not identity or identity in identifiers:
            raise ValueError(f"Row {line}: frame_id must be unique and nonempty")
        identifiers.add(identity)
        try:
            actual = int(row["reference_people"])
            predicted = int(row["detected_people"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Row {line}: counts must be nonnegative integers") from exc
        if actual < 0 or predicted < 0:
            raise ValueError(f"Row {line}: counts must be nonnegative integers")
        differences.append(predicted - actual)
    n = len(differences)
    return {
        "frames": n,
        "mae_people": round(sum(abs(d) for d in differences) / n, 4),
        "rmse_people": round(math.sqrt(sum(d * d for d in differences) / n), 4),
        "mean_error_people": round(sum(differences) / n, 4),
        "exact_count_fraction": round(sum(d == 0 for d in differences) / n, 4),
        "within_one_person_fraction": round(sum(abs(d) <= 1 for d in differences) / n, 4),
    }


SCENARIOS = {"clear", "crowded", "occluded", "low_light", "other"}


def scenario_breakdown(rows: list[dict[str, str]]) -> dict[str, dict[str, float | int]]:
    """Optional, human-labeled scene slices; no guesswork from image pixels.

    Counts from small slices are descriptive, NOT a population accuracy estimate.
    """
    slices: dict[str, list[dict[str, str]]] = {}
    for line, row in enumerate(rows, start=2):
        label = (row.get("scenario") or "").strip().lower()
        if label not in SCENARIOS:
            raise ValueError(f"Row {line}: scenario must be one of {', '.join(sorted(SCENARIOS))}")
        slices.setdefault(label, []).append(row)
    return {label: evaluate(group) for label, group in sorted(slices.items())}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "csv_path", type=Path, help="CSV with frame_id,reference_people,detected_people"
    )
    args = parser.parse_args()
    try:
        with args.csv_path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames or not {
                "frame_id",
                "reference_people",
                "detected_people",
            }.issubset(reader.fieldnames):
                raise ValueError("Required columns: frame_id,reference_people,detected_people")
            rows = list(reader)
            result = evaluate(rows)
            slices = scenario_breakdown(rows) if "scenario" in reader.fieldnames else None
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    output: dict[str, object] = {
        "scope": "Visible people per annotated frame, not tracking or entries/exits",
        **result,
    }
    if slices is not None:
        output["scenario_slices"] = slices
        output["slice_warning"] = (
            "Small or uneven scene slices are descriptive only; report frame counts with errors."
        )
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
