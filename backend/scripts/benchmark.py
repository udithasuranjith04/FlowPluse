"""Measure the generated fixture pipeline; never present these as YOLO/live results."""

import json
import platform
import resource
import time
from pathlib import Path

import numpy as np

from app.rules import RuleEngine
from app.schemas import demo_zones
from app.synthetic import render_frame
from app.tracking import Tracker
from app.vision import SyntheticDetector


def main() -> None:
    detector, tracker = SyntheticDetector(), Tracker()
    engine = RuleEngine("demo", demo_zones(), "REPLAY", detector.name)
    latencies, events = [], {}
    start = time.perf_counter()
    for i in range(160):
        frame = render_frame(i * 0.5)
        before = time.perf_counter()
        detections = detector.detect(frame)
        latencies.append((time.perf_counter() - before) * 1000)
        for event in engine.step(tracker.update(detections, i * 0.5), i * 0.5):
            events[event["id"]] = event
    elapsed = time.perf_counter() - start
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    report = {
        "scope": "Generated replay, color detector, tracker and rules; not YOLO or live accuracy",
        "platform": platform.platform(),
        "processor": platform.machine(),
        "python": platform.python_version(),
        "frames": 160,
        "scenario_seconds": 80,
        "elapsed_seconds": round(elapsed, 3),
        "offline_processing_fps": round(160 / elapsed, 2),
        "detector_p50_ms": round(float(np.percentile(latencies, 50)), 3),
        "detector_p95_ms": round(float(np.percentile(latencies, 95)), 3),
        "peak_rss_mb": round(peak / (1024 * 1024 if platform.system() == "Darwin" else 1024), 2),
        "events": {
            kind: sum(e["type"] == kind for e in events.values())
            for kind in ("potential_stopped_vehicle", "congestion_buildup")
        },
        "accuracy_evaluation": "Not performed on real footage",
    }
    output = Path("runtime/benchmark.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    if not all(report["events"].values()):
        raise SystemExit("Synthetic scenario did not produce both expected observation types")


if __name__ == "__main__":
    main()
