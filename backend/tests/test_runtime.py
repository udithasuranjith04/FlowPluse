import time

import cv2
import numpy as np
from fastapi.testclient import TestClient

from app.main import create_app
from app.schemas import demo_zones
from app.storage import Store


def wait_for(read, ready, timeout=20):
    deadline = time.monotonic() + timeout
    while True:
        value = read()
        if ready(value):
            return value
        assert time.monotonic() < deadline, f"Runtime did not become ready: {value}"
        time.sleep(0.1)


def test_running_replay_frames_events_review_and_worker_shutdown(settings):
    # Exercise real capture/inference threads and generated pixels, without a TCP server,
    # external source, detector mock, shared database or downloaded model.
    settings.autostart = True
    settings.camera_url = settings.replay_path = ""
    settings.save_evidence = False
    config = demo_zones()
    config.rules.target_fps = 4
    config.rules.min_track_age = 1
    config.rules.stationary_seconds = 2
    store = Store(settings.db_path)
    store.save_config("demo", config)
    store.close()

    with TestClient(create_app(settings)) as client:
        status = wait_for(
            lambda: client.get("/api/system/status").json(),
            lambda s: s["ai_state"] == "active" and s["processed_fps"] > 0,
        )
        assert status["mode"] == status["state"] == "REPLAY"
        assert status["model"].startswith("Synthetic color detector")
        assert status["active_tracks"] > 0
        assert status["latency_p95_ms"] > 0
        assert status["processing_delay_ms"] >= 0
        assert status["queue_depth"] <= 1
        assert status["last_error"] is None
        for overlays in ("true", "false"):
            response = client.get(f"/api/stream/frame.jpg?overlays={overlays}")
            assert response.status_code == 200
            assert response.headers["content-type"] == "image/jpeg"
            decoded = cv2.imdecode(np.frombuffer(response.content, np.uint8), cv2.IMREAD_COLOR)
            assert decoded is not None and decoded.shape == (540, 960, 3)
        with client.websocket_connect(
            "/ws/live", headers={"origin": "http://localhost:5173"}
        ) as socket:
            message = socket.receive_json()
            assert message["type"] == "status"
            assert message["data"]["ai_state"] == "active"

        result = wait_for(
            lambda: client.get("/api/events?type=potential_stopped_vehicle").json(),
            lambda events: events["total"] > 0,
        )
        event = result["items"][0]
        assert event["source_mode"] == "REPLAY"
        assert event["state"] == "active" and event["evidence_url"] is None
        assert (
            client.patch(
                f"/api/events/{event['id']}/review", json={"review_status": "acknowledged"}
            ).status_code
            == 200
        )

        workers = list(client.app.state.pipeline.threads)
        assert len(workers) == 2 and all(worker.is_alive() for worker in workers)
        stopped = client.post("/api/system/stop")
        assert stopped.status_code == 200
        assert stopped.json()["state"] == "OFFLINE"
        assert stopped.json()["ai_state"] == "paused"
        assert client.get("/api/stream/frame.jpg").status_code == 503
        assert all(not worker.is_alive() for worker in workers)
        saved = client.get(f"/api/events/{event['id']}").json()
        assert saved["state"] == "resolved" and saved["review_status"] == "acknowledged"

        assert client.post("/api/cameras/demo/activate").status_code == 200
        wait_for(
            lambda: client.get("/api/system/status").json(),
            lambda s: s["ai_state"] == "active" and s["processed_fps"] > 0,
        )
        restarted_workers = list(client.app.state.pipeline.threads)
        assert len(restarted_workers) == 2
    assert all(not worker.is_alive() for worker in restarted_workers)
    store = Store(settings.db_path)
    try:
        assert store.event(event["id"])["review_status"] == "acknowledged"
        assert store.get_config("demo", demo_zones()) == config
    finally:
        store.close()
