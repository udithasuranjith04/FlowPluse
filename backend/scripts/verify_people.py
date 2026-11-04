"""Live, read-only person-pipeline verification against a running local backend.

The operator must first consent and activate a real camera through the UI.
No images or identifiers are saved, and this does not establish accuracy.
"""

import argparse
import json
import time
from urllib.error import URLError
from urllib.request import urlopen


def verify(seconds: float) -> dict:
    deadline = time.monotonic() + seconds
    frame_ids: set[str] = set()
    samples = 0
    positive = False
    last = None
    while time.monotonic() < deadline:
        with urlopen("http://127.0.0.1:8000/api/system/status", timeout=3) as response:
            status = json.load(response)
        last = status
        if status.get("detection_target") != "person":
            raise ValueError("Selected source is not in person-detection mode.")
        if status.get("mode") != "LIVE" or not status.get("camera_id", "").startswith(
            "local-camera-"
        ):
            raise ValueError("Select and activate a real owned live camera in the UI first.")
        if status.get("frame_id"):
            frame_ids.add(status["frame_id"])
            samples += 1
        positive |= (status.get("visible_people") or 0) > 0
        time.sleep(0.5)
    if last is None:
        raise ValueError("No source status samples were received")
    return {
        "scope": "Running local live person detector; not detection/counting accuracy",
        "source": last["camera_id"],
        "model": last["model"],
        "state": last["state"],
        "samples": samples,
        "distinct_processed_frames": len(frame_ids),
        "positive_person_detection_observed": positive,
        "processed_fps_last": last.get("processed_fps"),
        "inference_ms_last": last.get("inference_ms"),
        "flow": last.get("flow"),
        "pass": len(frame_ids) >= 2 and last.get("ai_state") == "active",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, default=15)
    args = parser.parse_args()
    try:
        result = verify(args.seconds)
        print(json.dumps(result, indent=2))
        raise SystemExit(0 if result["pass"] else 1)
    except (URLError, ValueError, TimeoutError) as exc:
        print(json.dumps({"pass": False, "error": str(exc)}))
        raise SystemExit(1) from None
