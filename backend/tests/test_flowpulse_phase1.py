"""FlowPulse phase 1: person detection is opt-in, demo and vehicle rules stay honest."""

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.vision import YoloDetector


def test_detection_target_is_strict_and_reversible():
    assert Settings(_env_file=None).detection_target == "person"
    assert Settings(_env_file=None, detection_target="person").detection_target == "person"
    with pytest.raises(ValidationError):
        Settings(_env_file=None, detection_target="face")


def test_yolo_target_validation():
    with pytest.raises(ValueError, match="Detector target"):
        YoloDetector("missing.pt", "cpu", "face")


def test_person_status_suppresses_vehicle_rules(settings):
    from fastapi.testclient import TestClient

    from app.main import create_app

    settings.detection_target = "person"
    with TestClient(create_app(settings)) as client:
        status = client.get("/api/system/status").json()
        assert status["detection_target"] == "vehicle"  # Synthetic demo remains unchanged.
        pipeline = client.app.state.pipeline
        # This is an in-memory status test, not proof of real YOLO person inference.
        pipeline.camera_id = "local-camera-0"
        pipeline.mode = "LIVE"
        pipeline.state = "LIVE"
        pipeline.preview_only = False
        pipeline.continuous_frames_verified = True
        pipeline.visible_people = 2
        status = client.get("/api/system/status").json()
        assert status["detection_target"] == "person"
        assert status["visible_people"] == 2
        assert status["temporal_rules_enabled"] is False  # No configured zone or line.


def test_yolo_class_ids_are_person_only_when_opted_in(monkeypatch):
    """Check arguments forwarded to YOLO without downloading weights or importing Ultralytics."""
    import sys
    from types import ModuleType, SimpleNamespace

    import numpy as np

    class FakeResults:
        pass

    fake_module = ModuleType("ultralytics.engine.results")
    fake_module.Results = FakeResults
    monkeypatch.setitem(sys.modules, "ultralytics.engine.results", fake_module)

    received = []

    def predict(*args, **kwargs):
        received.append(kwargs["classes"])
        return [FakeResults()]

    detector = object.__new__(YoloDetector)
    detector.model = SimpleNamespace(predict=predict)
    detector.device = "cpu"
    detector.target = "person"
    detector._predict(np.zeros((64, 64, 3), dtype=np.uint8), 0.35)
    detector.target = "vehicle"
    detector._predict(np.zeros((64, 64, 3), dtype=np.uint8), 0.35)
    assert received == [[0], [2, 3, 5, 7]]
