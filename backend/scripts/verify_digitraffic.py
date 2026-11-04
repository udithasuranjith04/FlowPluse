"""Small opt-in real integration probe. Keeps images in memory and writes only a report."""

import argparse
import hashlib
import json
import time
from pathlib import Path

from app.config import Settings
from app.digitraffic import DigitrafficService, ProviderError, age
from app.vision import YoloDetector


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--station", help="Optional preferred station, with bounded fallback")
    parser.add_argument("--preset", help="Optional preferred preset, not a required active example")
    parser.add_argument(
        "--seek-positive",
        action="store_true",
        help="Try up to three fresh images for positive detections",
    )
    parser.add_argument("--tms", help="Optional independently selected official TMS station ID")
    args = parser.parse_args()
    settings = Settings()
    provider = DigitrafficService(settings.digitraffic_user)
    report: dict = {
        "success": False,
        "scope": "Real provider + local YOLO execution; not accuracy evaluation",
        "verified": [],
        "stage": "directory",
    }
    try:
        directory = provider.camera_stations()
        report["verified"].append(f"Official camera directory: {len(directory)} stations")
        report["stage"] = "camera_discovery"
        detector = None
        report["positive_vehicle_detection"] = False
        for camera, source, frame in provider.discover(args.station, args.preset):
            report["stage"] = "model_load"
            if detector is None:
                detector = YoloDetector(settings.model_path, settings.device)
            report["stage"] = "inference"
            started = time.perf_counter()
            detections = detector.detect(frame)
            inference_ms = round((time.perf_counter() - started) * 1000, 3)
            report.update(
                {
                    "model": detector.name,
                    "device": detector.device,
                    "station_id": camera["station_id"],
                    "station_metadata_check": provider.station_checks.get(camera["station_id"], {}),
                    "metadata_state_verified": camera.get("metadata_state_verified", False),
                    "preset_id": camera["preset_id"],
                    "source_url": camera["image_url"],
                    "image_sha256": source.digest.hex(),
                    "inference_frame_sha256": hashlib.sha256(frame.tobytes()).hexdigest(),
                    "source_timestamp": source.source_timestamp,
                    "timestamp_kind": source.timestamp_kind,
                    "image_age_seconds": age(source.source_timestamp),
                    "inference_ms": inference_ms,
                    "visible_vehicles": len(detections),
                    "dimensions": list(frame.shape[:2]),
                    "positive_vehicle_detection": bool(detections),
                    "detections": [
                        {"label": d.label, "confidence": d.confidence, "box": list(d.box)}
                        for d in detections
                    ],
                }
            )
            report["verified"].append(
                f"Official JPEG {camera['preset_id']} decoded; "
                f"actual local YOLO completed: {len(detections)} detections"
            )
            if detections or not args.seek_positive:
                break
        report["attempts"] = getattr(provider, "discovery_diagnostics", [])
        if detector is None:
            report["stage"] = "camera_discovery"
            raise ProviderError(
                "No usable fresh camera image found within the bounded discovery budget"
            )
        report["stage"] = "complete"
        if args.tms:
            try:
                report["tms"] = provider.tms(args.tms)
                report["verified"].append("Separate official TMS station queried")
            except ProviderError as exc:
                report["tms_error"] = str(exc)
        report["success"] = True
    except (ProviderError, RuntimeError, ValueError) as exc:
        report["error"] = str(exc)
        report["attempts"] = getattr(provider, "discovery_diagnostics", [])
    finally:
        provider.http.close()
    output = Path(
        "runtime/digitraffic-positive-verification.json"
        if args.seek_positive
        else "runtime/digitraffic-verification.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    if not report["success"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
