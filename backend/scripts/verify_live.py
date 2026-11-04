"""Explicit real-source acceptance probe. Never substitutes a file or generated frame."""

import argparse
import json
import tempfile
import time
from collections import Counter
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, build_opener

import cv2
import numpy as np

from app.config import Settings
from app.pipeline import Pipeline
from app.storage import Store


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--local",
        action="store_true",
        help="Open an isolated owned-camera pipeline; stop make dev first",
    )
    parser.add_argument(
        "--authorize-owned-camera",
        action="store_true",
        help="I control this device and permit local processing/display",
    )
    parser.add_argument("--device-index", type=int, choices=range(16), default=0)
    parser.add_argument("--seconds", type=int, choices=range(5, 61), default=15)
    parser.add_argument(
        "--require-vehicles",
        action="store_true",
        help="Require positive vehicles and a repeated moving image-plane track; not accuracy",
    )
    args = parser.parse_args()
    report: dict = {
        "scope": "Actual continuous source; no synthetic fallback, no accuracy claim",
        "success": False,
        "require_vehicle_tracks": args.require_vehicles,
        "milestones": {
            "model_loaded": "NOT VERIFIED",
            "real_image_inference": "NOT VERIFIED",
            "positive_vehicle_detection": "NOT VERIFIED",
            "continuous_decoding": "NOT VERIFIED",
            "live_browser_display": "NOT VERIFIED",
            "consecutive_tracking": "NOT VERIFIED",
            "real_temporal_observations": "NOT VERIFIED",
            "traffic_event_accuracy": "NOT VERIFIED",
        },
    }
    pipe = store = None
    seen: dict[str, dict] = {}
    track_ids: Counter = Counter()
    moving_ids: set[str] = set()
    selected_source = None
    opener = build_opener(ProxyHandler({}))
    started = time.monotonic()
    temporary = tempfile.TemporaryDirectory(prefix="roadpulse-live-")
    try:
        directory = temporary.name
        if args.local:
            if not args.authorize_owned_camera:
                raise RuntimeError(
                    "--local requires --authorize-owned-camera. No device was opened."
                )
            settings = Settings(
                autostart=False,
                save_evidence=False,
                database_url=f"sqlite:///{directory}/events.db",
                evidence_dir=Path(directory) / "evidence",
            )
            store = Store(settings.db_path)
            pipe = Pipeline(settings, store)
            pipe.activate_local(args.device_index)
        deadline = time.monotonic() + args.seconds
        latest = {}
        while time.monotonic() < deadline:
            if pipe:
                with pipe.lock:
                    latest, payload = pipe.status(), pipe.annotated
                    headers = {
                        "x-roadpulse-camera-id": latest["camera_id"],
                        "x-roadpulse-frame-id": latest["frame_id"],
                    }
            else:
                with opener.open("http://127.0.0.1:8000/api/system/status", timeout=3) as response:
                    latest = json.load(response)
                if latest["mode"] != "LIVE" or latest["camera_id"] == "demo":
                    raise RuntimeError(
                        "Select an authorized LIVE source in the dashboard first; "
                        "snapshots/replay/demo are not accepted."
                    )
                payload = None
                if latest.get("frame_id") and latest["ai_state"] == "active":
                    try:
                        with opener.open(
                            f"http://127.0.0.1:8000/api/stream/frame.jpg?camera_id={latest['camera_id']}&frame_id={latest['frame_id']}",
                            timeout=3,
                        ) as response:
                            payload, headers = response.read(8_000_001), response.headers
                    except HTTPError as exc:
                        if exc.code == 409:
                            # A newer real frame arrived; retry without mixing metadata.
                            continue
                        raise
            if selected_source is None:
                selected_source = latest["camera_id"]
            if latest["camera_id"] != selected_source:
                raise RuntimeError(
                    "Source switched during acceptance; rerun on one selected camera."
                )
            if args.require_vehicles and latest.get("preview_only"):
                raise RuntimeError(
                    "Confirm Start road monitoring after preview before the vehicle check."
                )
            if latest.get("frame_id") and latest.get("ai_state") == "active" and payload:
                if "Ultralytics" not in latest.get("model", ""):
                    raise RuntimeError("Actual Ultralytics detector is required.")
                if (
                    headers["x-roadpulse-frame-id"] != latest["frame_id"]
                    or headers["x-roadpulse-camera-id"] != latest["camera_id"]
                ):
                    raise RuntimeError("Image/status source or frame identity mismatch.")
                if (
                    len(payload) > 8_000_000
                    or cv2.imdecode(np.frombuffer(payload, np.uint8), cv2.IMREAD_COLOR) is None
                ):
                    raise RuntimeError("Processed image could not be decoded.")
                ident = latest["frame_id"]
                if ident not in seen:
                    seen[ident] = {
                        k: latest.get(k)
                        for k in (
                            "frame_id",
                            "frame_timestamp",
                            "visible_vehicles",
                            "detections",
                            "tracks",
                            "inference_ms",
                        )
                    }
                    track_ids.update(t["id"] for t in latest.get("tracks", []))
                    moving_ids.update(
                        t["id"]
                        for t in latest.get("tracks", [])
                        if t.get("image_plane_motion_per_second", 0) > 0.001
                    )
            time.sleep(0.1)
        report.update(
            {
                "source": latest.get("camera_id"),
                "model": latest.get("model"),
                "device": latest.get("device"),
                "format": latest.get("input_type"),
                "resolution": latest.get("resolution"),
                "capture_fps": latest.get("ingest_fps"),
                "processed_fps": latest.get("processed_fps"),
                "dropped_frames": latest.get("dropped_frames"),
                "last_error": latest.get("last_error"),
                "distinct_processed_frames": len(seen),
                "frames": list(seen.values())[:60],
                "track_ids_seen_in_multiple_frames": sum(
                    count >= 2 for count in track_ids.values()
                ),
                "repeated_tracks_with_image_plane_motion": sum(
                    track_ids[k] >= 2 for k in moving_ids
                ),
                "motion_threshold_diagonals_per_second": 0.001,
                "monitoring_zones_configured": latest.get("monitoring_zones_configured"),
                "temporal_rules_enabled": latest.get("temporal_rules_enabled"),
            }
        )
        if "Ultralytics" in latest.get("model", ""):
            report["milestones"]["model_loaded"] = "PASS"
        if seen:
            report["milestones"]["real_image_inference"] = "PASS"
        if len(seen) >= 2:
            report["milestones"]["continuous_decoding"] = "PASS"
        if any((s["visible_vehicles"] or 0) > 0 for s in seen.values()):
            report["milestones"]["positive_vehicle_detection"] = "PASS"
        if any(count >= 2 for count in track_ids.values()):
            report["milestones"]["consecutive_tracking"] = "PASS"
        report["success"] = (
            len(seen) >= 2
            and latest.get("state") == "LIVE"
            and latest.get("ai_state") == "active"
            and latest.get("continuous_frames_verified") is True
        )
        if args.require_vehicles:
            report["success"] = report["success"] and (
                report["milestones"]["positive_vehicle_detection"] == "PASS"
                and report["repeated_tracks_with_image_plane_motion"] > 0
            )
            if not report["success"]:
                report["error"] = (
                    "Vehicle acceptance not met. Aim a stationary owned camera safely at traffic; "
                    "require positive detections and a repeated moving image-plane track. "
                    "No road accuracy is implied."
                )
        if not report["success"]:
            report.setdefault(
                "error",
                (
                    latest.get("last_error")
                    or "Fewer than two distinct processed frames; "
                    "check permission/source diagnostics and move the camera view."
                ),
            )
    except (OSError, URLError, RuntimeError, ValueError, KeyError) as exc:
        report["error"] = (
            str(exc)
            if not isinstance(exc, (OSError, URLError))
            else (
                "Local backend/camera unavailable. Start make dev and select a real live source, "
                "or use --local --authorize-owned-camera."
            )
        )
    finally:
        if pipe:
            try:
                pipe.stop()
            except RuntimeError as exc:
                report["shutdown_error"] = str(exc)
                report["success"] = False
            finally:
                pipe.digitraffic.http.close()
        if store:
            store.close()
    temporary.cleanup()
    report["elapsed_seconds"] = round(time.monotonic() - started, 2)
    output = Path(
        "runtime/road-verification.json"
        if args.require_vehicles
        else "runtime/live-verification.json"
    )
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
