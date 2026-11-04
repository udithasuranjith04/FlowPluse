"""Optional actual installed YOLO execution on original generated imagery, not accuracy."""

import importlib.util
from pathlib import Path

import pytest

from app.synthetic import render_frame
from app.tracking import Tracker
from app.vision import YoloDetector

WEIGHTS = Path(__file__).resolve().parents[2] / "runtime/models/yolo11n.pt"


@pytest.mark.skipif(
    importlib.util.find_spec("ultralytics") is None or not WEIGHTS.is_file(),
    reason="Optional Ultralytics/local YOLO11n weights are not installed",
)
def test_actual_yolo_load_and_cpu_inference_on_generated_pixels():
    detector = YoloDetector(str(WEIGHTS), "cpu")
    assert "Ultralytics" in detector.name and detector.device == "cpu"
    tracker = Tracker()
    for index in range(2):
        detections = detector.detect(render_frame(index * 0.5))
        assert all(d.label in {"car", "truck", "bus", "motorcycle"} for d in detections)
        assert all(0 <= d.confidence <= 1 for d in detections)
        tracks = tracker.update(detections, index * 0.5)
        assert len(tracks) == len(detections)
    # Zero detections are valid here; these pixels are not a road-camera accuracy fixture.


def test_yolo_result_mapping_and_anonymous_tracking_with_mock_predictions():
    """Explicit mock positive boxes test adapter mapping, not real YOLO accuracy."""
    from types import SimpleNamespace

    class Values:
        def __init__(self, values):
            self.values = values

        def cpu(self):
            return self

        def tolist(self):
            return self.values

    detector = object.__new__(YoloDetector)
    detector.device = "cpu"
    detector.model = SimpleNamespace(names={2: "car"})
    detector._predict = lambda *args: SimpleNamespace(
        boxes=SimpleNamespace(
            xyxyn=Values([[0.1, 0.2, 0.3, 0.4]]),
            conf=Values([0.83]),
            cls=Values([2]),
        )
    )
    detections = detector.detect(render_frame(0))
    assert detections[0].label == "car" and detections[0].confidence == 0.83
    tracker = Tracker()
    first = tracker.update(detections, 0)[0]
    assert tracker.update(detections, 0.5)[0].id == first.id
    tracker.reset()
    assert tracker.update(detections, 1)[0].id != first.id


@pytest.mark.skipif(
    importlib.util.find_spec("ultralytics") is None or not WEIGHTS.is_file(),
    reason="Optional Ultralytics/local YOLO11n weights are not installed",
)
def test_configured_generated_video_uses_real_yolo_then_switches_to_demo(settings, tmp_path):
    """Real decode + YOLO + worker + API, using our generated clip, no external media."""
    import time
    from datetime import date

    import cv2
    from fastapi.testclient import TestClient

    from app.main import create_app

    video = tmp_path / "original-generated.avi"
    writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"MJPG"), 10, (960, 540))
    assert writer.isOpened()
    for index in range(40):
        writer.write(render_frame(index * 0.1))
    writer.release()
    settings.camera_id = "original-fixture"
    settings.replay_path = str(video)
    settings.model_path = str(WEIGHTS)
    settings.camera_provider = "RoadPulse generated test"
    settings.camera_region = "Local test"
    settings.camera_analysis_authorized = settings.camera_redisplay_authorized = True
    settings.camera_permission_notes = "Original generated geometry created by this test"
    settings.camera_permission_checked = date.today().isoformat()
    with TestClient(create_app(settings)) as client:
        assert client.post("/api/cameras/original-fixture/activate").status_code == 200
        deadline = time.monotonic() + 15
        while True:
            status = client.get("/api/system/status").json()
            if status["ai_state"] == "active":
                break
            assert time.monotonic() < deadline, status
            time.sleep(0.1)
        assert "Ultralytics" in status["model"]
        assert status["device"] == "cpu" and status["input_type"] == "local_video"
        assert status["source_kind"] == "REPLAY"
        assert client.get("/api/stream/frame.jpg").status_code == 200
        old_workers = list(client.app.state.pipeline.threads)
        assert client.post("/api/cameras/demo/activate").status_code == 200
        assert all(not worker.is_alive() for worker in old_workers)
        assert client.get("/api/system/status").json()["camera_id"] == "demo"
