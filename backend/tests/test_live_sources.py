"""Source boundary tests use mock HTTP/capture objects; no provider media is fetched."""

from io import BytesIO

import cv2
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.sources import SnapshotSource, SourceError, VideoSource, input_type
from app.synthetic import render_frame


class ImageResponse(BytesIO):
    headers = {"Content-Type": "image/jpeg"}


def test_http_format_classification():
    assert input_type("image/jpeg") == "snapshot"
    assert input_type("application/octet-stream", b"\xff\xd8\xff") == "snapshot"
    assert input_type("multipart/x-mixed-replace; boundary=frame") == "mjpeg"
    assert input_type("application/vnd.apple.mpegurl") == "hls"
    assert input_type("text/plain", b"#EXTM3U\n") == "hls"
    with pytest.raises(SourceError, match="metadata"):
        input_type("text/html")


def test_bounded_snapshot_decoding_and_live_image_rejection(settings, monkeypatch):
    _, encoded = cv2.imencode(".jpg", render_frame(0))
    monkeypatch.setattr("app.sources.open_http", lambda *args: ImageResponse(encoded.tobytes()))
    source = SnapshotSource("https://camera.example/image", settings)
    assert source.continuous is False
    assert source.read().shape == (540, 960, 3)
    with pytest.raises(SourceError, match="snapshot"):
        VideoSource("https://camera.example/image", settings=settings)
    monkeypatch.setattr("app.sources.open_http", lambda *args: ImageResponse(b"invalid"))
    with pytest.raises(SourceError, match="decoded"):
        source.read()
    monkeypatch.setattr("app.sources.open_http", lambda *args: ImageResponse(b"x" * 8_000_001))
    with pytest.raises(SourceError, match="8 MB"):
        source.read()


def test_failed_capture_is_released_without_exposing_source(monkeypatch):
    class Capture:
        released = False

        def isOpened(self):
            return False

        def release(self):
            self.released = True

    capture = Capture()
    monkeypatch.setattr(cv2, "VideoCapture", lambda *args: capture)
    with pytest.raises(SourceError) as exc:
        VideoSource("rtsp://user:SECRET@camera.example/private")
    assert capture.released and "SECRET" not in str(exc.value)


def test_invalid_replay_startup_stays_offline_with_actionable_error(settings):
    settings.autostart = True
    settings.replay_path = "missing-private-file.mp4"
    with TestClient(create_app(settings)) as client:
        status = client.get("/api/system/status").json()
        assert status["state"] == "OFFLINE" and status["camera_id"] == "configured"
        assert "Replay file missing" in status["last_error"]
        assert "missing-private-file" not in str(status)
        assert not client.app.state.pipeline.threads
        assert client.post("/api/cameras/demo/activate").status_code == 200
        assert client.get("/api/system/status").json()["camera_id"] == "demo"


def test_missing_url_live_never_autostarts_synthetic(settings):
    settings.autostart = True
    settings.camera_mode = "live"
    settings.camera_url = settings.replay_path = ""
    with TestClient(create_app(settings)) as client:
        status = client.get("/api/system/status").json()
        assert status["state"] == "OFFLINE"
        assert "Camera URL missing" in status["last_error"]
        assert not client.app.state.pipeline.threads


def test_snapshot_scheme_and_redirect_private_host_are_blocked(settings, monkeypatch):
    import socket

    from app.sources import CheckedRedirects, validate_source

    settings.camera_mode = "snapshot"
    settings.camera_url = "rtsp://camera.example/image"
    settings.camera_analysis_authorized = settings.camera_redisplay_authorized = True
    settings.camera_permission_notes = "Mock owned-source test"
    settings.camera_permission_checked = "2026-10-31"
    with pytest.raises(SourceError, match="Snapshots require"):
        validate_source(settings)
    settings.camera_url = "https://camera.example/image"
    settings.camera_allowed_hosts = "camera.example"
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args: [(2, 1, 6, "", ("127.0.0.1", 80))])
    with pytest.raises(SourceError, match="Private-network"):
        CheckedRedirects(settings).redirect_request(None, None, 302, "", {}, settings.camera_url)


def test_worker_reconnects_failed_source_and_snapshot_suppresses_tracks(settings, monkeypatch):
    """Mock transport/detector to test worker reconnection, not real camera access."""
    import time
    from datetime import date
    from pathlib import Path

    from app.tracking import Detection

    settings.camera_mode = "snapshot"
    settings.camera_url = "https://camera.example/image"
    settings.camera_provider = settings.camera_region = "Mock source"
    settings.camera_allowed_hosts = "camera.example"
    settings.camera_source_page = settings.camera_terms_url = "https://camera.example/terms"
    settings.camera_permission_notes = "Mock permission for a transport regression test"
    settings.camera_permission_checked = date.today().isoformat()
    settings.camera_analysis_authorized = settings.camera_redisplay_authorized = True
    settings.snapshot_interval_seconds = 1
    settings.model_path = str(settings.db_path.parent / "mock-model.pt")
    Path(settings.model_path).touch()
    monkeypatch.setattr("app.pipeline.validate_source", lambda s: s.camera_url)

    class MockDetector:
        name = "Mock YOLO adapter lifecycle test"
        device = "cpu"
        device_note = None

        def __init__(self, *args):
            pass

        def detect(self, *args):
            return [Detection((0.1, 0.2, 0.3, 0.4), "car", 0.8)]

    class MockSnapshot:
        input_type = "snapshot"
        opens = 0

        def __init__(self, *args):
            type(self).opens += 1
            self.failed = type(self).opens == 1

        def read(self):
            if self.failed:
                raise SourceError("Mock source disconnected")
            return render_frame(0)

        def close(self):
            pass

    monkeypatch.setattr("app.pipeline.YoloDetector", MockDetector)
    monkeypatch.setattr("app.pipeline.SnapshotSource", MockSnapshot)
    with TestClient(create_app(settings)) as client:
        assert client.post("/api/cameras/configured/activate").status_code == 200
        deadline = time.monotonic() + 8
        while True:
            status = client.get("/api/system/status").json()
            if status["ai_state"] == "active":
                break
            assert time.monotonic() < deadline, status
            time.sleep(0.05)
        assert status["reconnect_count"] >= 1
        assert "snapshot_no_tracking" in status["quality_flags"]
        assert status["active_tracks"] == 0
        assert client.get("/api/events").json()["total"] == 0
        assert client.get("/api/stream/frame.jpg").status_code == 200
