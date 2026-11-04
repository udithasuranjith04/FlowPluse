from uuid import uuid4

from app.config import Settings
from app.storage import Store


def observation():
    return {
        "id": str(uuid4()),
        "camera_id": "demo",
        "type": "potential_stopped_vehicle",
        "state": "active",
        "review_status": "unreviewed",
        "started_at": "2026-10-31T10:00:00Z",
        "ended_at": None,
        "quality_flags": [],
        "evidence_url": None,
    }


def test_health_errors_and_validation(client):
    assert client.get("/api/health").json()["status"] == "ok"
    assert client.get("/api/events?limit=0").status_code == 422
    response = client.get("/api/cameras/missing/zones")
    assert response.status_code == 404 and "error" in response.json()
    assert client.get("/api/stream/frame.jpg").status_code == 503
    assert client.get("/api/events?since=2026-11-01&until=2026-10-01").status_code == 400


def test_zone_persistence_and_validation(client, settings, fast_config):
    assert client.put("/api/cameras/demo/zones", json=fast_config.model_dump()).status_code == 200
    store = Store(settings.db_path)
    assert store.get_config("demo", fast_config).zones[0].name == "Test lane"
    store.close()
    invalid = fast_config.model_dump()
    invalid["zones"][0]["points"] = [[0, 0], [1, 1]]
    assert client.put("/api/cameras/demo/zones", json=invalid).status_code == 422


def test_event_review_filters_export_and_restart(client, settings):
    event = observation()
    client.app.state.store.put_event(event)
    response = client.patch(
        f"/api/events/{event['id']}/review", json={"review_status": "false_alarm"}
    )
    assert response.status_code == 200
    assert client.get("/api/events?review_status=unreviewed").json()["total"] == 0
    assert client.get("/api/events?review_status=false_alarm").json()["total"] == 1
    assert client.get("/api/events?offset=1").json()["items"] == []
    assert "false_alarm" in client.get("/api/events/export?format=csv").text
    assert len(client.get("/api/events/export?format=json").json()) == 1
    # Repeated worker updates must not overwrite the human's review.
    client.app.state.store.put_event(event)
    store = Store(settings.db_path)
    assert store.event(event["id"])["review_status"] == "false_alarm"
    store.close()
    assert (
        client.patch(f"/api/events/{event['id']}/review", json={"review_status": "bad"}).status_code
        == 422
    )


def test_origin_and_host_boundaries(client):
    assert (
        client.post("/api/system/stop", headers={"Origin": "https://untrusted.example"}).status_code
        == 403
    )
    assert client.get("/api/health", headers={"Host": "untrusted.example"}).status_code == 400


def test_upstream_url_never_serialized(settings):
    settings.camera_url = "https://user:secret@camera.example/video?token=PRIVATE"
    settings.camera_terms_url = "https://provider.example/terms?token=TERMS_SECRET#hidden"
    text = str(settings.cameras())
    for secret in ("PRIVATE", "TERMS_SECRET", "user:", "secret@", "/video"):
        assert secret not in text
    assert Settings(_env_file=None).save_evidence is False


def test_websocket_contract(client):
    with client.websocket_connect("/ws/live", headers={"origin": "http://localhost:5173"}) as ws:
        message = ws.receive_json()
        assert message["version"] == 1 and message["type"] == "status"


def test_same_origin_api_documentation_can_submit(client):
    response = client.post("/api/system/stop", headers={"Origin": "http://testserver"})
    assert response.status_code == 200


def test_websocket_status_continues_across_browser_reconnections(client):
    for _ in range(3):
        with client.websocket_connect(
            "/ws/live", headers={"origin": "http://127.0.0.1:5173"}
        ) as socket:
            first = socket.receive_json()
            second = socket.receive_json()
            assert first["type"] == second["type"] == "status"
            assert first["version"] == second["version"] == 1
            assert second["data"]["state"] == "OFFLINE"
    assert client.get("/api/health").json()["status"] == "ok"
