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
            result = evaluate(list(reader))
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(
        json.dumps(
            {
                "scope": "Visible people per annotated frame, not tracking or entries/exits",
                **result,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
