"""Real weights on locally generated pixels. Execution smoke, never an accuracy test."""

import argparse
import hashlib
import json
import time
from pathlib import Path

from app.config import Settings
from app.synthetic import render_frame
from app.tracking import Tracker
from app.vision import YoloDetector


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", choices=["cpu", "mps"], default="cpu")
    args = parser.parse_args()
    weights = Path(Settings().model_path)
    start = time.perf_counter()
    detector = YoloDetector(str(weights), args.device)
    tracker = Tracker()
    counts = []
    timings = []
    for index in range(5):
        frame = render_frame(index * 0.5)
        before = time.perf_counter()
        detections = detector.detect(frame)
        timings.append(round((time.perf_counter() - before) * 1000, 3))
        tracker.update(detections, index * 0.5)
        counts.append(len(detections))
    report = {
        "scope": "Real YOLO on generated geometry; no accuracy or positive tracking validation",
        "model": detector.name,
        "requested_device": args.device,
        "actual_device": detector.device,
        "device_note": detector.device_note,
        "weights_sha256": hashlib.sha256(weights.read_bytes()).hexdigest(),
        "frames": 5,
        "detection_counts": counts,
        "inference_ms_including_first_warmup": timings,
        "elapsed_seconds": round(time.perf_counter() - start, 3),
    }
    output = Path(f"runtime/model-smoke-{args.device}.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
