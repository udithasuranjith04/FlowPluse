import cv2
import numpy as np

from app.quality import ViewStability
from app.storage import Store


def test_shift_memory_off_by_default_opt_in_and_erase(client):
    path = "/api/privacy/shift-memory"
    initial = client.get(path).json()
    assert initial["enabled"] is False and initial["saved_shifts"] == []
    store = client.app.state.store
    assert not store.archive_shift(
        "local-camera-1",
        "none",
        {
            "processed_samples": 350,
            "elapsed_seconds": 250,
            "average_visible": 4.2,
            "peak_visible": 7,
        },
    )
    assert client.put(path, json={"enabled": True}).json()["enabled"] is True
    assert not store.archive_shift(
        "local-camera-1",
        "none",
        {
            "processed_samples": 10,
            "elapsed_seconds": 5,
            "average_visible": 3.0,
            "peak_visible": 5,
        },
    )
    assert store.archive_shift(
        "local-camera-1",
        "none",
        {
            "processed_samples": 350,
            "elapsed_seconds": 250,
            "average_visible": 4.2,
            "peak_visible": 7,
        },
    )
    assert store.saved_shifts("local-camera-1", "none")[0]["average_visible"] == 4.2
    assert store.saved_shifts("local-camera-1", "top") == []
    assert client.delete(path).json()["saved_shifts"] == []
    assert store.saved_shifts("local-camera-1", "none") == []


def test_shift_memory_persists_only_aggregates_between_store_instances(settings):
    store = Store(settings.db_path)
    store.set_shift_memory(True)
    store.archive_shift(
        "local-camera-2",
        "none",
        {
            "processed_samples": 360,
            "elapsed_seconds": 270,
            "average_visible": 3.1,
            "peak_visible": 6,
        },
    )
    store.close()
    saved = Store(settings.db_path)
    try:
        items = saved.saved_shifts("local-camera-2", "none")
        assert len(items) == 1 and items[0]["peak_visible"] == 6
        assert set(items[0]) == {
            "created_at",
            "processed_samples",
            "elapsed_seconds",
            "average_visible",
            "peak_visible",
        }
    finally:
        saved.close()


def test_view_stability_detects_global_pans_not_small_person_motion():
    rng = np.random.default_rng(17)
    first = rng.integers(0, 255, size=(180, 320, 3), dtype=np.uint8)
    tracker = ViewStability()
    assert not tracker.update(first, 0.0)
    translated = cv2.warpAffine(first, np.float32([[1, 0, 22], [0, 1, 10]]), (320, 180))
    assert tracker.update(translated, 0.5)
    assert tracker.update(translated, 1.5)
    assert not tracker.update(translated, 4.5)


def test_shift_memory_excludes_short_legacy_records_and_requires_duration(settings):
    store = Store(settings.db_path)
    try:
        store.set_shift_memory(True)
        short = {
            "processed_samples": 400,
            "elapsed_seconds": 60,
            "average_visible": 3.0,
            "peak_visible": 6,
        }
        assert not store.archive_shift("local-camera-1", "none", short)
        short["elapsed_seconds"] = 260
        short["processed_samples"] = 200
        assert not store.archive_shift("local-camera-1", "none", short)
        short["processed_samples"] = 400
        assert store.archive_shift("local-camera-1", "none", short)
        assert len(store.saved_shifts("local-camera-1", "none")) == 1
    finally:
        store.close()


def test_moved_view_cannot_be_archived_as_comparable_shift(settings, monkeypatch):
    from app.pipeline import Pipeline

    store = Store(settings.db_path)
    store.set_shift_memory(True)
    pipeline = Pipeline(settings, store)
    try:
        pipeline.camera_id = "local-camera-1"
        pipeline.state = "LIVE"
        monkeypatch.setattr(
            pipeline.auto_insights,
            "snapshot",
            lambda: {
                "session_summary": {
                    "processed_samples": 400,
                    "elapsed_seconds": 280,
                    "average_visible": 5.0,
                    "peak_visible": 9,
                }
            },
        )
        pipeline.view_shift_detected = True
        assert pipeline.status()["view_shift_detected"] is True
        pipeline.stop()
        assert store.saved_shifts("local-camera-1", "none") == []
    finally:
        store.close()


def test_retired_testing_only_flag_is_rejected(client):
    response = client.post(
        "/api/local-camera/preview",
        json={
            "device_index": 0,
            "analysis_authorized": True,
            "redisplay_authorized": True,
            "testing_only": True,
        },
    )
    assert response.status_code == 422
    assert client.post("/api/testing/video", content=b"video").status_code == 404
