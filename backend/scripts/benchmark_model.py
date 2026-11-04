"""Benchmark an explicitly authorized local replay with the optional real detector."""

import hashlib
import json
import platform
import time
from pathlib import Path

import numpy as np

from app.config import Settings
from app.sources import VideoSource, validate_source
from app.vision import YoloDetector


def main() -> None:
    settings = Settings()
    if settings.camera_mode != "replay" or not settings.replay_path:
        raise SystemExit(
            "Configure a permitted ROADPULSE_REPLAY_PATH and camera mode replay first."
        )
    target = validate_source(settings)
    detector = YoloDetector(settings.model_path, settings.device)
    source = VideoSource(target, replay=True)
    timings: list[float] = []
    detected: list[int] = []
    shape = None
    try:
        # Explicit warmup excluded from timing. No frames are retained or written.
        for _ in range(5):
            frame = source.read()
            if frame is None:
                raise SystemExit("Replay delivered no frame during warmup.")
            detector.detect(frame)
        for _ in range(100):
            frame = source.read()
            if frame is None:
                raise SystemExit("Replay interrupted during measurement.")
            shape = [frame.shape[1], frame.shape[0]]
            start = time.perf_counter()
            detections = detector.detect(frame, 0.35)
            timings.append((time.perf_counter() - start) * 1000)
            detected.append(len(detections))
    finally:
        source.close()
    report = {
        "scope": "Actual local pretrained detector on operator-authorized replay",
        "platform": platform.platform(),
        "processor": platform.machine(),
        "python": platform.python_version(),
        "detector": detector.name,
        "weights_sha256": hashlib.sha256(Path(settings.model_path).read_bytes()).hexdigest(),
        "replay_loops": source.epoch,
        "device": settings.device,
        "frame_dimensions": shape,
        "warmup_frames": 5,
        "measured_frames": len(timings),
        "detector_p50_ms": round(float(np.percentile(timings, 50)), 3),
        "detector_p95_ms": round(float(np.percentile(timings, 95)), 3),
        "detector_only_fps": round(len(timings) * 1000 / sum(timings), 2),
        "total_vehicle_detections": sum(detected),
        "accuracy_evaluation": "Not measured; detections are not ground-truth labels",
        "source": "Authorized local replay; path intentionally omitted",
    }
    output = Path("runtime/benchmark-model.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
