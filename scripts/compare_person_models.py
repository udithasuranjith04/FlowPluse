#!/usr/bin/env python3
"""Local, read-only model comparison on operator-authorized video frames.

Requires existing weight files; never downloads weights, records frames, or
stores identities. Without human reference counts or boxes this is only a
speed/count comparison, not an accuracy benchmark.
"""

import argparse
import csv
import math
import statistics
import sys
import time
from pathlib import Path

import cv2

# This script is launched from the FlowPulse project root after `make setup`.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.evaluation_metrics import compare_boxes
from app.person_detail import PersonDetailScanner
from app.tracking import Detection
from app.vision import YoloDetector

Box = tuple[float, float, float, float]


def read_references(path: Path) -> list[tuple[float, int]]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = csv.DictReader(handle)
        if not {"seconds", "visible_people"}.issubset(rows.fieldnames or []):
            raise ValueError("Reference CSV needs seconds,visible_people columns")
        entries = [(float(row["seconds"]), int(row["visible_people"])) for row in rows]
    if not (1 <= len(entries) <= 30) or any(t < 0 or count < 0 for t, count in entries):
        raise ValueError("Provide 1–30 nonnegative times and visible-person counts")
    return entries


def read_boxes(path: Path) -> dict[float, list[Box]]:
    """Read normalized rectangles grouped by sample time, without person IDs."""
    boxes: dict[float, list[Box]] = {}
    total_boxes = 0
    with path.open(encoding="utf-8", newline="") as handle:
        rows = csv.DictReader(handle)
        if not {"seconds", "x1", "y1", "x2", "y2"}.issubset(rows.fieldnames or []):
            raise ValueError("Boxes CSV needs seconds,x1,y1,x2,y2 columns")
        for row in rows:
            second = float(row["seconds"])
            box: Box = (
                float(row["x1"]),
                float(row["y1"]),
                float(row["x2"]),
                float(row["y2"]),
            )
            if not (
                math.isfinite(second)
                and second >= 0
                and all(math.isfinite(coord) for coord in box)
                and 0 <= box[0] < box[2] <= 1
                and 0 <= box[1] < box[3] <= 1
            ):
                raise ValueError(
                    "Boxes must have finite, nonnegative times and normalized rectangles"
                )
            boxes.setdefault(second, []).append(box)
            total_boxes += 1
            if len(boxes) > 50 or total_boxes > 1000:
                raise ValueError("Use at most 50 reference frames and 1,000 boxes")
    if not boxes:
        raise ValueError("Boxes CSV has no reference boxes")
    return boxes


def annotation_metrics(
    predictions: list[list[Detection]], references: list[list[Box]]
) -> dict[str, float | int]:
    """Aggregate frame-wise, one-to-one IoU precision/recall against manual boxes."""
    frame_scores = [
        compare_boxes(predicted, expected)
        for predicted, expected in zip(predictions, references, strict=True)
    ]
    tp = sum(result.true_positive for result in frame_scores)
    fp = sum(result.false_positive for result in frame_scores)
    missed = sum(result.missed for result in frame_scores)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + missed) if tp + missed else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "tp": tp,
        "fp": fp,
        "missed": missed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--video", type=Path, required=True, help="Permitted local video path"
    )
    parser.add_argument(
        "--baseline", type=Path, default=Path("runtime/models/yolo11n.pt")
    )
    parser.add_argument(
        "--candidate", type=Path, help="Optional second locally installed model"
    )
    references = parser.add_mutually_exclusive_group()
    references.add_argument(
        "--reference", type=Path, help="Count CSV: seconds,visible_people"
    )
    references.add_argument(
        "--boxes", type=Path, help="Per-person boxes CSV: seconds,x1,y1,x2,y2"
    )
    parser.add_argument("--device", choices=["cpu", "mps"], default="cpu")
    args = parser.parse_args()
    paths = [args.baseline] + ([args.candidate] if args.candidate else [])
    if not args.video.is_file() or any(not p.is_file() for p in paths):
        parser.error(
            "Video and all requested model weights must exist locally; no download is made"
        )
    try:
        reference = read_references(args.reference) if args.reference else None
        reference_boxes = read_boxes(args.boxes) if args.boxes else None
    except (ValueError, OSError, KeyError) as exc:
        parser.error(str(exc))
    capture = cv2.VideoCapture(str(args.video))
    if not capture.isOpened():
        parser.error("Cannot decode the local video with OpenCV")
    try:
        duration = capture.get(cv2.CAP_PROP_FRAME_COUNT) / max(
            capture.get(cv2.CAP_PROP_FPS), 0.1
        )
        if not 0 < duration < 7 * 86400:
            parser.error("Video duration is invalid; specify a decodable recording")
        sample_times = (
            [row[0] for row in reference]
            if reference
            else sorted(reference_boxes)
            if reference_boxes
            else [duration * (i + 1) / 13 for i in range(12)]
        )
        frames = []
        for seconds in sample_times:
            if not 0 <= seconds < duration:
                parser.error(
                    f"Sample {seconds}s lies outside video duration {duration:.1f}s"
                )
            capture.set(cv2.CAP_PROP_POS_MSEC, seconds * 1000)
            ok, frame = capture.read()
            if not ok or frame is None:
                parser.error(f"Cannot decode a sample at {seconds:.1f}s")
            frames.append(frame)
    finally:
        capture.release()
    print("Local count and performance comparison (no frames saved)")
    for weights in paths:
        try:
            detector = YoloDetector(str(weights), args.device, target="person")
        except (ImportError, RuntimeError) as exc:
            parser.error(f"Could not load local weights {weights.name}: {exc}")
        scanner = PersonDetailScanner()
        durations = []
        counts = []
        boxes_per_sample = []
        for frame in frames:
            start = time.perf_counter()
            raw = detector.detect(frame, 0.35)
            merged = scanner.augment(detector, frame, raw, 0.35)
            high_confidence = [d for d in merged if d.confidence >= 0.35]
            boxes_per_sample.append(high_confidence)
            counts.append(len(high_confidence))
            durations.append((time.perf_counter() - start) * 1000)
        print(f"\n{weights.name}: {len(frames)} sampled frames")
        print(f"  Counts by sample: {counts}")
        print(f"  Median inference+closeups: {statistics.median(durations):.0f} ms")
        print(f"  Slowest sample: {max(durations):.0f} ms")
        if reference:
            errors = [
                abs(pred - actual) for pred, (_, actual) in zip(counts, reference)
            ]
            print(
                f"  Mean absolute COUNT error vs manual counts: {statistics.mean(errors):.2f}"
            )
        elif reference_boxes:
            expected = [reference_boxes[second] for second in sample_times]
            scores = annotation_metrics(boxes_per_sample, expected)
            errors = [abs(pred - len(label)) for pred, label in zip(counts, expected)]
            print(f"  Annotated count MAE: {statistics.mean(errors):.2f}")
            print(
                f"  IoU>=0.50 precision {scores['precision']:.3f}, "
                f"recall {scores['recall']:.3f}, F1 {scores['f1']:.3f} "
                f"(matched {scores['tp']}, false boxes {scores['fp']}, "
                f"missed {scores['missed']})"
            )
        else:
            print("  No human reference: accuracy and recall CANNOT be inferred.")
    print(
        "\nCaution: video sampling/people overlap can change counts; test authorized fixed views."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
