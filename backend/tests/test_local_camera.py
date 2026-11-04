"""Mock camera lifecycle/consent and generated-video decoder regressions, not road validation."""

import hashlib
import queue
import time
from pathlib import Path
from types import SimpleNamespace

import cv2
import pytest
from fastapi.testclient import TestClient

from app.avfoundation import opencv_camera_order
from app.local_camera import LocalCameraSource, capture_device, list_devices
from app.main import create_app
from app.sources import SourceError, VideoSource
from app.synthetic import render_frame
from app.tracking import Detection


def test_avfoundation_camera_indices_match_opencv_sorted_unique_ids():
    # macOS discovery order can differ from OpenCV's sorted capture indices.
    # In particular, never map a virtual camera selection to a built-in webcam.
    unsorted = [
        {"index": 0, "name": "Mac camera", "device_id": "z-mac"},
        {"index": 1, "name": "OBS Virtual Camera", "device_id": "a-obs"},
        {"index": 2, "name": "iPhone", "device_id": "m-iphone"},
    ]
    ordered = opencv_camera_order(unsorted)
    assert [(item["index"], item["device_id"]) for item in ordered] == [
        (0, "a-obs"),
        (1, "m-iphone"),
        (2, "z-mac"),
    ]
    # Producing the corrected list must not mutate the discovery data.
    assert unsorted[0]["index"] == 0
    assert unsorted[1]["index"] == 1


def test_native_device_discovery_preserves_camera_identity(monkeypatch):
    import json

    rows = [
        {"index": 0, "name": "Mock Mac camera", "device_id": "mac"},
        {"index": 3, "name": "Mock iPhone", "device_id": "phone"},
    ]
    monkeypatch.setattr("app.local_camera.platform.system", lambda: "Darwin")
    monkeypatch.setattr(
        "app.local_camera.subprocess.run",
        lambda *a, **kw: SimpleNamespace(returncode=0, stdout=json.dumps(rows)),
    )
    assert list_devices()["devices"] == rows
    from app.local_camera import resolve_device

    assert resolve_device("phone")["index"] == 3
    with pytest.raises(SourceError, match="disconnected or unavailable"):
        resolve_device("missing")
    monkeypatch.setattr(
        "app.local_camera.subprocess.run",
        lambda *a, **kw: SimpleNamespace(returncode=0, stdout="[]"),
    )
    assert list_devices()["discovery_available"]
    assert "no cameras" in list_devices()["message"]
    monkeypatch.setattr(
        "app.local_camera.subprocess.run",
        lambda *a, **kw: SimpleNamespace(returncode=1, stdout=""),
    )
    assert not list_devices()["discovery_available"]


def test_local_reader_timeouts_errors_and_cleanup_are_bounded(monkeypatch):
    class Frames(queue.Queue):
        def cancel_join_thread(self):
            pass

        def close(self):
            self.closed = True

    frames = Frames(maxsize=1)
    alive = iter([True, True, False])
    process = SimpleNamespace(
        start=lambda: None,
        join=lambda **kw: None,
        is_alive=lambda: next(alive),
        terminate=lambda: None,
        kill=lambda: None,
    )
    context = SimpleNamespace(
        Queue=lambda **kw: frames,
        Event=lambda: SimpleNamespace(set=lambda: None),
        Process=lambda **kw: process,
    )
    monkeypatch.setattr("app.local_camera.mp.get_context", lambda _: context)
    source = LocalCameraSource(0, timeout=0.01)
    with pytest.raises(SourceError, match="timed out"):
        source.read()
    frames.put(("frame", (render_frame(0), time.monotonic(), 3)))
    assert source.read().shape == (540, 960, 3)
    assert source.dropped_frames == 2
    frames.put(("frame", (render_frame(0), time.monotonic() - 4, 4)))
    with pytest.raises(SourceError, match="old buffered"):
        source.read()
    frames.put(("error", "Mock permission denial"))
    with pytest.raises(SourceError, match="permission denial"):
        source.read()
    source.close()
    assert frames.closed
    with pytest.raises(SourceError, match="index"):
        LocalCameraSource(16)


def test_unreaped_capture_never_claims_successful_stop(settings):
    from app.pipeline import Pipeline
    from app.storage import Store

    actions = []
    source = LocalCameraSource.__new__(LocalCameraSource)
    source.stop = SimpleNamespace(set=lambda: actions.append("signal"))
    source.process = SimpleNamespace(
        join=lambda **kw: actions.append(kw["timeout"]),
        is_alive=lambda: True,
        terminate=lambda: actions.append("terminate"),
        kill=lambda: actions.append("kill"),
    )
    source.frames = SimpleNamespace(
        cancel_join_thread=lambda: None, close=lambda: actions.append("queue_closed")
    )
    with pytest.raises(SourceError, match="still closing"):
        source.close()
    assert actions == ["signal", 0.5, "terminate", 1, "kill", 1, "queue_closed"]
    store = Store(settings.db_path)
    pipeline = Pipeline(settings, store)
    pipeline.device_released = False
    try:
        with pytest.raises(SourceError, match="did not confirm release"):
            pipeline.stop()
        assert pipeline.status()["state"] == "STOPPING"
        assert not pipeline.status()["device_released"]
    finally:
        pipeline.digitraffic.http.close()
        store.close()


def test_capture_worker_decodes_genuine_capture_api_and_releases(monkeypatch):
    """Capture object is mocked; verify real pixels are forwarded without substitution."""
    frame = render_frame(1)
    stop = SimpleNamespace(is_set=lambda: not frames.empty())
    frames = queue.Queue(maxsize=1)
    capture = SimpleNamespace(
        isOpened=lambda: True,
        set=lambda *a: True,
        read=lambda: (True, frame),
        release=lambda: released.append(True),
    )
    released = []
    monkeypatch.setattr(cv2, "VideoCapture", lambda *args: capture)
    capture_device(0, frames, stop)
    kind, (received, captured, sequence) = frames.get_nowait()
    assert kind == "frame" and received is frame and captured <= time.monotonic()
    assert sequence == 1
    assert released == [True]


def test_native_video_decoder_on_generated_file(tmp_path):
    """Actual OpenCV/FFmpeg decoding of generated video; no external footage claim."""
    path = tmp_path / "generated.avi"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 5, (960, 540))
    assert writer.isOpened()
    for offset in (0, 2, 4):
        writer.write(render_frame(offset))
    writer.release()
    source = VideoSource(str(path), replay=True)
    try:
        frames = [source.read() for _ in range(4)]
        assert all(frame is not None and frame.shape == (540, 960, 3) for frame in frames)
        assert (
            hashlib.sha256(frames[0].tobytes()).digest()
            != hashlib.sha256(frames[1].tobytes()).digest()
        )
        assert source.epoch == 1
    finally:
        source.close()


def test_owned_live_pipeline_tracks_resets_and_switches_without_demo_pixels(settings, monkeypatch):
    settings.target_fps = 15
    settings.model_path = str(settings.db_path.parent / "mock.pt")
    Path(settings.model_path).touch()

    class Camera:
        input_type = "mock_owned_camera"
        opens = 0

        def __init__(self, index):
            assert index == 2
            type(self).opens += 1
            self.epoch, self.index, self.first = 0, 0, self.opens == 1

        def read(self):
            time.sleep(0.04)
            self.index += 1
            if self.first and self.index == 6:
                raise SourceError("Mock owned camera disconnect")
            return render_frame(self.index * 0.1)

        def close(self):
            pass

    class Detector:
        name, device, device_note = "Mock YOLO lifecycle", "cpu", None

        def __init__(self, *args):
            pass

        def detect(self, frame, confidence):
            return [Detection((0.1, 0.2, 0.3, 0.4), "car", 0.9)]

    monkeypatch.setattr("app.pipeline.LocalCameraSource", Camera)
    monkeypatch.setattr("app.pipeline.YoloDetector", Detector)
    with TestClient(create_app(settings)) as client:
        assert (
            client.post("/api/local-camera/activate", json={"device_index": 2}).status_code == 409
        )
        assert Camera.opens == 0
        response = client.post(
            "/api/local-camera/activate",
            json={
                "device_index": 2,
                "analysis_authorized": True,
                "redisplay_authorized": True,
            },
        )
        assert response.status_code == 200
        initial_ids = set()
        recovered_ids = set()
        deadline = time.monotonic() + 7
        while time.monotonic() < deadline:
            status = client.get("/api/system/status").json()
            if status["ai_state"] == "active" and status["tracks"]:
                target = recovered_ids if Camera.opens > 1 else initial_ids
                target.add(status["tracks"][0]["id"])
                if initial_ids and recovered_ids:
                    break
            time.sleep(0.02)
        assert initial_ids and recovered_ids and initial_ids.isdisjoint(recovered_ids)
        assert status["capabilities"]["continuous_video"]
        assert status["capabilities"]["supports_tracking"]
        assert not status["capabilities"]["capture_timestamp_available"]
        assert status["source_kind"] == "LOCAL LIVE CAMERA" and status["mode"] == "LIVE"
        assert status["resolution"] == [960, 540]
        assert status["visible_vehicles"] == 1 and status["active_tracks"] == 1
        image = client.get(f"/api/stream/frame.jpg?camera_id={status['camera_id']}")
        assert image.status_code == 200
        assert image.headers["x-roadpulse-camera-id"] == "local-camera-2"
        assert client.get("/api/stream/frame.jpg?camera_id=demo").status_code == 409
        assert client.post("/api/cameras/demo/activate").status_code == 200
        assert client.get("/api/system/status").json()["camera_id"] == "demo"
        assert client.get("/api/stream/frame.jpg?camera_id=local-camera-2").status_code == 409


def test_inference_from_retired_capture_session_cannot_publish(settings, monkeypatch):
    from app.pipeline import Pipeline
    from app.storage import Store

    store = Store(settings.db_path)
    pipeline = Pipeline(settings, store)
    pipeline.capture_generation = 1

    class Detector:
        name = "Mock capture-boundary detector"

        def detect(self, *args):
            # A disconnect occurred while inference was in progress.
            pipeline.capture_generation = 2
            pipeline.stop_event.set()
            return [Detection((0.1, 0.2, 0.3, 0.4), "car", 0.9)]

    monkeypatch.setattr("app.pipeline.SyntheticDetector", Detector)
    pipeline.frames.put(
        (
            render_frame(0),
            time.monotonic(),
            "test receipt",
            1_000_000,
            None,
            "local receipt",
            None,
            None,
        )
    )
    try:
        pipeline._process()
        assert pipeline.raw is None and pipeline.annotated is None
        assert pipeline.frame_id is None and pipeline.visible_vehicles is None
        assert not pipeline.track_details
    finally:
        pipeline.digitraffic.http.close()
        store.close()


def test_owned_ip_camera_uses_ownership_evidence_without_fake_public_terms(settings, monkeypatch):
    from datetime import date

    from app.sources import validate_source

    settings.camera_mode = "live"
    settings.camera_url = "rtsp://192.168.1.10/owned"
    settings.camera_owned = True
    settings.camera_allowed_hosts = "192.168.1.10"
    settings.camera_analysis_authorized = settings.camera_redisplay_authorized = True
    settings.camera_permission_notes = "Mock operator-owned IP camera permission"
    settings.camera_permission_checked = date.today().isoformat()
    settings.camera_provider = settings.camera_region = "Operator-owned test"
    settings.model_path = str(settings.db_path.parent / "mock.pt")
    Path(settings.model_path).touch()
    monkeypatch.setattr(
        "app.sources.socket.getaddrinfo", lambda *a: [(2, 1, 6, "", ("192.168.1.10", 554))]
    )
    assert settings.source_issues() == []
    with pytest.raises(SourceError, match="Private-network"):
        validate_source(settings)
    settings.camera_allow_private = True
    assert validate_source(settings) == settings.camera_url
    settings.camera_owned = False
    assert any("terms" in issue for issue in settings.source_issues())


def test_preview_pause_resume_stop_and_switch_release_selected_device(
    settings, monkeypatch, fast_config
):
    """Mock device/YOLO, actual threads and HTTP: not hardware/road acceptance."""
    settings.target_fps = 15
    settings.model_path = str(settings.db_path.parent / "mock.pt")
    Path(settings.model_path).touch()
    lifecycle = []

    class Camera:
        input_type = "mock_owned_camera"

        def __init__(self, index):
            self.index, self.tick, self.epoch = index, 0, 0
            lifecycle.append(("open", index))

        def read(self):
            time.sleep(0.025)
            self.tick += 1
            return render_frame(self.tick * 0.1)

        def close(self):
            lifecycle.append(("release", self.index))

    class Detector:
        name, device, device_note = "Mock YOLO preview lifecycle", "cpu", None

        def __init__(self, *args):
            pass

        def detect(self, *args):
            return [Detection((0.1, 0.2, 0.3, 0.4), "car", 0.9)]

    monkeypatch.setattr("app.pipeline.LocalCameraSource", Camera)
    monkeypatch.setattr("app.pipeline.YoloDetector", Detector)

    def ready(client):
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            status = client.get("/api/system/status").json()
            if status["ai_state"] == "active" and status["continuous_frames_verified"]:
                return status
            time.sleep(0.025)
        pytest.fail(str(status))

    consent = {"device_index": 2, "analysis_authorized": True, "redisplay_authorized": True}
    with TestClient(create_app(settings)) as client:
        assert client.post("/api/system/pause").status_code == 409
        assert client.post("/api/system/resume").status_code == 409
        assert client.post("/api/local-camera/preview", json=consent).status_code == 200
        preview = ready(client)
        assert preview["preview_only"] and not preview["temporal_rules_enabled"]
        assert preview["monitoring_zones_configured"] is False
        assert client.get("/api/events").json()["total"] == 0
        assert (
            client.put(
                "/api/cameras/local-camera-2/zones", json=fast_config.model_dump()
            ).status_code
            == 200
        )
        assert not client.get("/api/system/status").json()["temporal_rules_enabled"]
        assert client.post("/api/local-camera/activate", json=consent).status_code == 200
        monitoring = ready(client)
        assert not monitoring["preview_only"] and monitoring["temporal_rules_enabled"]
        paused = client.post("/api/system/pause").json()
        assert paused["state"] == "PAUSED" and paused["mode"] == "LIVE"
        assert paused["device_released"] and paused["ai_state"] == "paused"
        assert paused["processed_fps"] == paused["ingest_fps"] == 0
        assert paused["active_tracks"] == 0 and not paused["temporal_rules_enabled"]
        assert paused["frame_id"]
        with client.app.state.pipeline.lock:
            client.app.state.pipeline.last_processed -= 60
        assert client.get("/api/system/status").json()["state"] == "PAUSED"
        assert client.get(f"/api/stream/frame.jpg?frame_id={paused['frame_id']}").status_code == 200
        assert lifecycle[-1] == ("release", 2)
        assert client.post("/api/system/resume").status_code == 200
        resumed = ready(client)
        assert resumed["control_revision"] > paused["control_revision"]
        assert resumed["tracks"][0]["id"] != monitoring["tracks"][0]["id"]
        switched = client.post("/api/local-camera/activate", json={**consent, "device_index": 1})
        assert switched.status_code == 200
        ready(client)
        opened = lifecycle.index(("open", 1))
        assert lifecycle[opened - 1] == ("release", 2)
        workers = list(client.app.state.pipeline.threads)
        stopped = client.post("/api/system/stop").json()
        assert lifecycle[-1] == ("release", 1)
        assert stopped["device_released"] and stopped["state"] == "OFFLINE"
        assert stopped["frame_id"] is None and stopped["visible_vehicles"] is None
        assert client.get("/api/stream/frame.jpg").status_code == 503
        assert not client.app.state.pipeline.threads and all(
            not worker.is_alive() for worker in workers
        )
        assert client.post("/api/system/stop").status_code == 200  # idempotent
