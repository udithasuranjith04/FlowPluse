"""Quick-start counts are bounded, source-specific, and never sold as a census."""

from collections import deque


def test_count_trend_is_not_video_storage(client):
    pipeline = client.app.state.pipeline
    pipeline.camera_id = "local-camera-1"
    pipeline.settings.detection_target = "person"
    pipeline.people_count_history.extend(
        [
            {"at": "2026-11-02T10:00:00Z", "people": 2},
            {"at": "2026-11-02T10:00:01Z", "people": 3},
        ]
    )
    status = client.get("/api/system/status").json()
    assert status["people_count_history"] == [
        {"at": "2026-11-02T10:00:00Z", "people": 2},
        {"at": "2026-11-02T10:00:01Z", "people": 3},
    ]
    assert not any("image" in row or "track_id" in row for row in status["people_count_history"])
    pipeline.stop()
    assert client.get("/api/system/status").json()["people_count_history"] == []


def test_count_history_is_bounded(client):
    pipeline = client.app.state.pipeline
    assert isinstance(pipeline.people_count_history, deque)
    for i in range(130):
        pipeline.people_count_history.append({"at": str(i), "people": i})
    assert len(pipeline.people_count_history) == 90
    assert pipeline.people_count_history[0]["people"] == 40
