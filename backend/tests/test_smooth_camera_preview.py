"""Live display must never interfere with the privacy-safe AI capture lifecycle."""

import asyncio
import time

import cv2
import numpy as np

from app.main import create_app
from app.pipeline import Pipeline
from app.storage import Store
from app.synthetic import render_frame


def test_camera_preview_publishes_latest_jpeg_only_and_never_crosses_generations(settings):
    store = Store(settings.db_path)
    pipeline = Pipeline(settings, store)
    try:
        frame = render_frame(0)
        pipeline.camera_id = "local-camera-2"
        pipeline.capture_generation = 3
        pipeline.publish_camera_preview(frame, time.monotonic(), 3)
        assert pipeline.preview_sequence == 1
        first = pipeline.preview_jpeg
        assert first and first.startswith(b"\xff\xd8")
        decoded = cv2.imdecode(np.frombuffer(first, np.uint8), cv2.IMREAD_COLOR)
        assert decoded is not None and decoded.shape[:2] == frame.shape[:2]

        pipeline.publish_camera_preview(render_frame(1), time.monotonic(), 3)
        assert pipeline.preview_sequence == 2
        assert pipeline.preview_jpeg != first

        # In-flight JPEG encodes from previous cameras must never become visible.
        pipeline.capture_generation = 4
        second = pipeline.preview_jpeg
        pipeline.publish_camera_preview(render_frame(2), time.monotonic(), 3)
        assert pipeline.preview_sequence == 2 and pipeline.preview_jpeg == second
        pipeline.stop_event.set()
        pipeline.publish_camera_preview(render_frame(3), time.monotonic(), 4)
        assert pipeline.preview_sequence == 2
    finally:
        pipeline.digitraffic.http.close()
        store.close()


def test_smooth_stream_rejects_nonselected_or_offline_camera(client):
    assert client.get("/api/stream/local-preview.mjpg?camera_id=demo").status_code == 409
    assert client.get("/api/stream/local-preview.mjpg?camera_id=local-camera-9").status_code == 409


def test_smooth_stream_yields_latest_frame_and_ends_on_camera_change(settings):
    from fastapi.testclient import TestClient

    class RequestStub:
        async def is_disconnected(self):
            return False

    async def verify(app):
        pipeline = app.state.pipeline
        with pipeline.lock:
            pipeline.camera_id = "local-camera-1"
            pipeline.state = "LIVE"
            pipeline.capture_generation = 7
            pipeline.preview_jpeg = b"\xff\xd8FAKE-JPEG\xff\xd9"
            pipeline.preview_capture_time = time.monotonic()
            pipeline.preview_sequence = 1
            pipeline.error = None
        route = next(
            r for r in app.routes if getattr(r, "path", None) == "/api/stream/local-preview.mjpg"
        )
        result = await route.endpoint(RequestStub(), camera_id="local-camera-1")
        assert result.media_type.startswith("multipart/x-mixed-replace")
        assert result.headers["cache-control"].startswith("no-store")
        iterator = result.body_iterator
        packet = await asyncio.wait_for(iterator.__anext__(), timeout=1)
        assert packet.startswith(b"--frame\r\nContent-Type: image/jpeg")
        assert b"FAKE-JPEG" in packet
        # Once the camera/source generation changes the connection must terminate.
        with pipeline.lock:
            pipeline.capture_generation = 8
        try:
            await asyncio.wait_for(iterator.__anext__(), timeout=1)
            raise AssertionError("Stale video should have stopped")
        except StopAsyncIteration:
            pass

    with TestClient(create_app(settings)) as client:
        asyncio.run(verify(client.app))
