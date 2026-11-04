"""People-flow filters must not silently mix old vehicle observations."""

from uuid import uuid4


def event(kind: str):
    return {
        "id": str(uuid4()),
        "type": kind,
        "camera_id": "local-camera-1",
        "state": "resolved",
        "review_status": "unreviewed",
        "started_at": "2026-11-02T10:00:00Z",
        "ended_at": None,
        "quality_flags": [],
        "features": {},
        "evidence_url": None,
    }


def test_people_events_are_queryable_and_legacy_archive_is_separate(client):
    for kind in (
        "potential_stopped_vehicle",
        "congestion_buildup",
        "extended_dwell",
        "possible_queue_buildup",
    ):
        client.app.state.store.put_event(event(kind))
    people = client.get("/api/events?domain=people")
    assert people.status_code == 200
    assert people.json()["total"] == 2
    assert {e["type"] for e in people.json()["items"]} == {
        "extended_dwell",
        "possible_queue_buildup",
    }
    assert client.get("/api/events?type=extended_dwell").json()["total"] == 1
    legacy = client.get("/api/events?domain=legacy").json()
    assert legacy["total"] == 2
    export = client.get("/api/events/export?format=csv&domain=people")
    assert export.status_code == 200
    assert "extended_dwell" in export.text
    assert "potential_stopped_vehicle" not in export.text
