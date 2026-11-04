"""Explicit mocked API contracts; external Fintraffic connectivity is tested separately."""

import gzip
import hashlib
import json
import time
from datetime import UTC, datetime, timedelta

import cv2
import httpx
import numpy as np
import pytest

from app.digitraffic import (
    API,
    Cached,
    DigitrafficHTTP,
    DigitrafficService,
    DigitrafficSnapshot,
    ProviderError,
    age,
    presets,
    stations,
    timestamp,
    tms_measurements,
    usable,
    vetted_url,
)
from app.synthetic import render_frame

IMAGE = "https://weathercam.digitraffic.fi/C1451601.jpg"


def feature():
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [24.5, 60.1]},
        "properties": {
            "id": "C14516",
            "name": "Mock official station",
            "state": "OK",
            "collectionStatus": "GATHERING",
            "presets": [
                {
                    "id": "C1451601",
                    "presentationName": "Road orientation",
                    "inCollection": True,
                    "imageUrl": IMAGE,
                }
            ],
        },
    }


def test_geojson_presets_filter_unavailable_and_vet_image_path():
    camera = feature()
    assert stations({"type": "FeatureCollection", "features": [camera]})[0]["latitude"] == 60.1
    result = presets(camera)[0]
    assert result["id"] == "digitraffic-C1451601" and result["image_url"] == IMAGE
    assert result["mode"] == "SNAPSHOT" and result["license_status"] == "CC BY 4.0"
    assert result["analysis_authorized"] and result["redisplay_authorized"]
    camera["properties"]["presets"][0]["inCollection"] = False
    assert presets(camera) == []
    camera["properties"]["presets"][0]["inCollection"] = True
    camera["properties"]["state"] = "FAULT"
    assert presets(camera) == []
    camera["properties"]["state"] = "OK"
    camera["properties"]["presets"][0]["imageUrl"] = "https://127.0.0.1/private.jpg"
    with pytest.raises(ProviderError):
        presets(camera)


@pytest.mark.parametrize("state", [None, "OK", "FAULT", 42])
def test_missing_state_is_unknown_not_an_automatic_availability_grant(state):
    detail = feature()
    detail["properties"]["state"] = state
    if state == 42:
        with pytest.raises(ProviderError, match="state type"):
            presets(detail)
    elif state == "FAULT":
        assert usable(detail["properties"]) is False and presets(detail) == []
    else:
        assert usable(detail["properties"]) is (True if state == "OK" else None)
        assert presets(detail)[0]["metadata_state_verified"] is (state == "OK")
    detail["properties"].pop("state")
    detail["properties"]["collectionStatus"] = "REMOVED"
    assert presets(detail) == []
    incomplete_summary = {"id": "C01504"}
    assert usable(incomplete_summary, summary=True) is None
    assert usable(incomplete_summary) is False


@pytest.mark.parametrize("fresh", [True, False])
def test_unknown_state_yields_only_valid_fresh_real_jpeg_pixels(fresh):
    """Mock public response with omitted state; actual JPEG decode/freshness gate."""
    detail = feature()
    detail["properties"].pop("state")
    captured = (datetime.now(UTC) - timedelta(minutes=1 if fresh else 60)).isoformat()
    _, jpeg = cv2.imencode(".jpg", render_frame(0))

    class HTTP:
        def get(self, *args, **kwargs):
            return Cached(jpeg.tobytes(), "image/jpeg", None, None, 0)

        def json(self, path, *args):
            return (
                {"presets": [{"id": "C1451601", "measuredTime": captured}]}
                if path.endswith("/data")
                else detail
            )

    source = DigitrafficSnapshot(DigitrafficService(http=HTTP()), presets(detail)[0])
    if fresh:
        expected = cv2.imdecode(jpeg, cv2.IMREAD_COLOR)
        np.testing.assert_array_equal(source.read(), expected)
        assert source.source_timestamp == timestamp(captured)
    else:
        with pytest.raises(ProviderError, match="older than"):
            source.read()


def test_verified_alternatives_exclude_failed_station_and_cache_image_probes():
    """Mock directory/media, actual decoding. Not a currently available public camera claim."""
    import copy

    bad = feature()
    bad["properties"]["id"] = "C01504"
    good = copy.deepcopy(feature())
    good["properties"]["id"] = "C19999"
    good["properties"].pop("state")
    good["properties"]["presets"][0].update(
        id="C1999901", imageUrl="https://weathercam.digitraffic.fi/C1999901.jpg"
    )
    captured = datetime.now(UTC).isoformat()
    _, jpeg = cv2.imencode(".jpg", render_frame(0))
    fetches = []

    class HTTP:
        def json(self, path, *args):
            if path == "/api/weathercam/v1/stations":
                return {"type": "FeatureCollection", "features": [bad, good]}
            assert "C01504" not in path
            return (
                {"presets": [{"id": "C1999901", "measuredTime": captured}]}
                if path.endswith("/data")
                else good
            )

        def get(self, url, *args, **kwargs):
            fetches.append(url)
            return Cached(jpeg.tobytes(), "image/jpeg", None, None, 0)

    service = DigitrafficService(http=HTTP())
    result = service.verified_alternatives("C01504")
    assert len(result) == 1 and result[0]["id"] == "digitraffic-C1999901"
    assert result[0]["source_timestamp"] == timestamp(captured)
    assert result[0]["image_verified_at"]
    assert result[0]["metadata_state_verified"] is False
    assert service.verified_alternatives("C01504") == result
    assert len(fetches) == 1


@pytest.mark.parametrize(
    "url",
    [
        "http://weathercam.digitraffic.fi/C1451601.jpg",
        "https://weathercam.digitraffic.fi.evil/C1451601.jpg",
        "https://tie.digitraffic.fi/private",
        IMAGE + "?token=x",
        "https://user:secret@weathercam.digitraffic.fi/C1451601.jpg",
    ],
)
def test_restricts_hosts_paths_and_credentials(url):
    with pytest.raises(ProviderError):
        vetted_url(url)


def test_conditional_304_and_compressed_json_are_cached_without_new_content():
    calls = []

    def handle(request):
        calls.append(request)
        assert request.headers["Digitraffic-User"] == "RoadPulse-AI/test"
        assert "gzip" in request.headers["Accept-Encoding"]
        if len(calls) == 1:
            return httpx.Response(
                200,
                headers={
                    "Content-Type": "application/json",
                    "Content-Encoding": "gzip",
                    "ETag": '"one"',
                },
                content=gzip.compress(b'{"features": []}'),
            )
        assert request.headers["If-None-Match"] == '"one"'
        return httpx.Response(304)

    http = DigitrafficHTTP("RoadPulse-AI/test", httpx.MockTransport(handle))
    try:
        first = http.get(API + "/api/weathercam/v1/stations", 600)
        assert json.loads(first.body) == {"features": []}
        assert http.get(API + "/api/weathercam/v1/stations", 600) is first
        assert len(calls) == 1
        first.next_check = 0
        http.last_request = 0
        assert http.get(API + "/api/weathercam/v1/stations", 600) is first
        assert len(calls) == 2
    finally:
        http.close()


@pytest.mark.parametrize("code", [403, 404, 429, 500, 503, 302])
def test_http_failures_backoff_and_do_not_follow_redirects(code):
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(
            code, headers={"Retry-After": "120", "Location": "https://127.0.0.1/"}
        )

    http = DigitrafficHTTP(transport=httpx.MockTransport(handle))
    try:
        with pytest.raises(ProviderError, match=f"HTTP {code}"):
            http.get(IMAGE, 600, image=True)
        with pytest.raises(ProviderError, match="backoff"):
            http.get(IMAGE, 600, image=True)
        assert len(calls) == 1
        if code == 429:
            assert http.failures[IMAGE][1] > time.monotonic() + 100
            with pytest.raises(ProviderError, match="backoff"):
                http.get(API + "/api/tms/v1/stations", 600)
    finally:
        http.close()


def test_snapshot_jpeg_timestamp_and_unchanged_image_deduplication():
    captured = datetime.now(UTC).isoformat()
    _, jpeg = cv2.imencode(".jpg", render_frame(0))

    class HTTP:
        def __init__(self):
            self.item = Cached(jpeg.tobytes(), "image/jpeg", '"one"', None, 0)

        def get(self, *args, **kwargs):
            return self.item

        def json(self, path, *args):
            if path.endswith("/data"):
                return {"presets": [{"id": "C1451601", "measuredTime": captured}]}
            return feature()

    http = HTTP()
    service = DigitrafficService(http=http)
    source = DigitrafficSnapshot(service, presets(feature())[0])
    assert source.read().shape == (540, 960, 3)
    assert source.source_timestamp == timestamp(captured)
    assert source.read() is None
    # A 200 response with a new ETag but identical bytes must also avoid inference.
    http.item = Cached(jpeg.tobytes(), "image/jpeg", '"two"', None, 0)
    assert source.read() is None
    assert source.source_timestamp == timestamp(captured)
    http.item = Cached(b"invalid", "image/jpeg", None, None, 0)
    with pytest.raises(ProviderError, match="JPEG"):
        source.read()


def test_snapshot_timestamp_unknown_and_old_measurements_are_honest():
    old = timestamp((datetime.now(UTC) - timedelta(hours=1)).isoformat())
    assert age(old) > 3500
    assert timestamp("not a date") is None
    assert timestamp((datetime.now(UTC) + timedelta(hours=1)).isoformat()) is None


def test_tms_values_units_missing_data_and_origins():
    now = datetime.now(UTC).isoformat()
    old = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    definitions = {"sensors": [{"id": 1, "name": "MOCK_SPEED_SUUNTA1", "unit": "km/h"}]}
    payload = {
        "stations": [
            {
                "id": 123,
                "sensorValues": [
                    {"id": 1, "sensorValue": 0, "measuredTime": now},
                    {
                        "id": 2,
                        "sensorValue": 120,
                        "sensorUnit": "kpl/h",
                        "measuredTime": old,
                        "name": "MOCK_PASSINGS_60MIN_SUUNTA2",
                    },
                    {"id": 3, "sensorValue": -1, "sensorUnit": "km/h", "measuredTime": now},
                    {"id": 4, "sensorValue": None, "sensorUnit": "km/h", "measuredTime": now},
                ],
            }
        ]
    }
    rows = tms_measurements(payload, definitions, "123")
    assert len(rows) == 2 and rows[0]["value"] == 0
    assert rows[0]["unit"] == "km/h" and rows[1]["stale"]
    assert rows[1]["direction"] == "2"
    assert rows[1]["window_minutes_from_sensor_name"] == 60
    assert all("not YOLO" in row["origin"] for row in rows)
    assert tms_measurements(payload, definitions, "999") == []


def test_snapshot_pipeline_api_same_image_not_reinferred_and_switch_to_demo(settings, monkeypatch):
    """Mock Fintraffic HTTP and detector; verify worker/API wiring and dedup, not real data."""
    from pathlib import Path

    from fastapi.testclient import TestClient

    from app.main import create_app
    from app.tracking import Detection

    settings.digitraffic_enabled = True
    settings.model_path = str(settings.db_path.parent / "mock.pt")
    Path(settings.model_path).touch()
    now = datetime.now(UTC).isoformat()
    _, jpeg = cv2.imencode(".jpg", render_frame(0))
    calls = []

    def handle(request):
        calls.append(str(request.url))
        if request.url.host == "weathercam.digitraffic.fi":
            return httpx.Response(
                200, headers={"Content-Type": "image/jpeg", "ETag": '"one"'}, content=jpeg.tobytes()
            )
        if request.url.path.endswith("/data"):
            return httpx.Response(200, json={"presets": [{"id": "C1451601", "measuredTime": now}]})
        return httpx.Response(200, json=feature())

    class Detector:
        name = "Mock YOLO for provider wiring test"
        device = "cpu"
        device_note = None
        calls = 0

        def __init__(self, *args):
            pass

        def detect(self, *args):
            type(self).calls += 1
            # Verify the inference worker receives this HTTP JPEG's decoded
            # pixels, not the prior demo frame or a different fixture.
            expected = cv2.imdecode(jpeg, cv2.IMREAD_COLOR)
            np.testing.assert_array_equal(args[0], expected)
            return [Detection((0.1, 0.2, 0.3, 0.4), "car", 0.82)]

    monkeypatch.setattr("app.pipeline.YoloDetector", Detector)
    service = DigitrafficService(http=DigitrafficHTTP(transport=httpx.MockTransport(handle)))
    service.camera_presets("C14516")
    with TestClient(create_app(settings)) as client:
        pipeline = client.app.state.pipeline
        pipeline.digitraffic.http.close()
        pipeline.digitraffic = service
        service.http.last_request = 0
        assert client.post("/api/cameras/digitraffic-C1451601/activate").status_code == 200
        deadline = time.monotonic() + 10
        while True:
            status = client.get("/api/system/status").json()
            if status["ai_state"] == "active":
                break
            assert time.monotonic() < deadline, status
            time.sleep(0.05)
        assert status["source_kind"] == "CURRENT CAMERA SNAPSHOT"
        expected = cv2.imdecode(jpeg, cv2.IMREAD_COLOR)
        assert status["source_image_sha256"] == hashlib.sha256(jpeg.tobytes()).hexdigest()
        assert status["frame_id"] == hashlib.sha256(expected.tobytes()).hexdigest()
        assert status["source_timestamp"] == timestamp(now)
        assert status["visible_vehicles"] == 1 and status["active_tracks"] == 0
        assert status["detections"][0]["confidence"] == 0.82
        assert status["temporal_rules_enabled"] is False
        assert client.get("/api/stream/annotated.mjpg").status_code == 409
        image = client.get(
            f"/api/stream/frame.jpg?camera_id={status['camera_id']}&frame_id={status['frame_id']}"
        )
        assert image.status_code == 200
        assert image.headers["x-roadpulse-frame-id"] == status["frame_id"]
        assert image.headers["x-roadpulse-source-image-sha256"] == status["source_image_sha256"]
        assert client.get("/api/stream/frame.jpg?camera_id=demo").status_code == 409
        assert client.get("/api/stream/frame.jpg?frame_id=wrong").status_code == 409
        previous = status["frame_timestamp"]
        time.sleep(2.2)
        assert Detector.calls == 1
        assert client.get("/api/system/status").json()["frame_timestamp"] == previous
        assert client.get("/api/events").json()["total"] == 0
        with pipeline.lock:
            pipeline.source_timestamp = timestamp(
                (datetime.now(UTC) - timedelta(hours=1)).isoformat()
            )
        assert client.get("/api/system/status").json()["state"] == "STALE"
        assert client.post("/api/cameras/demo/activate").status_code == 200
        assert client.get("/api/system/status").json()["camera_id"] == "demo"
        assert client.get("/api/system/status").json()["source_timestamp"] is None
        assert client.get("/api/stream/frame.jpg?camera_id=digitraffic-C1451601").status_code == 409


@pytest.mark.parametrize("case", ["mime", "size", "json", "304"])
def test_provider_invalid_payloads_are_visible_errors(case):
    def handle(request):
        if case == "304":
            return httpx.Response(304)
        if case == "size":
            return httpx.Response(
                200, headers={"Content-Type": "image/jpeg"}, content=b"x" * 8_000_001
            )
        if case == "json":
            return httpx.Response(
                200, headers={"Content-Type": "application/json"}, content=b"invalid"
            )
        return httpx.Response(200, headers={"Content-Type": "text/html"}, content=b"not an image")

    http = DigitrafficHTTP(transport=httpx.MockTransport(handle))
    try:
        with pytest.raises(ProviderError):
            if case == "json":
                http.json("/api/weathercam/v1/stations")
            else:
                http.get(IMAGE, 600, image=True)
    finally:
        http.close()


def test_dynamic_discovery_skips_inactive_example_and_unavailable_images(monkeypatch):
    """Mock current directory, not a claim that the documentation example is inactive."""
    provider = DigitrafficService()
    monkeypatch.setattr(
        provider,
        "camera_stations",
        lambda: [
            {"id": "C14516", "available": False},
            {"id": "C10001", "available": True},
            {"id": "C10002", "available": True},
        ],
    )
    seen = []

    def choices(station):
        seen.append(station)
        return [
            {"id": f"digitraffic-{station}01", "preset_id": f"{station}01", "station_id": station}
        ]

    monkeypatch.setattr(provider, "camera_presets", choices)
    monkeypatch.setattr(provider, "camera", lambda ident: {"id": ident})

    class Snapshot:
        source_timestamp = datetime.now(UTC).isoformat()

        def __init__(self, service, camera):
            self.camera = camera

        def read(self):
            if "C10001" in self.camera["id"]:
                raise ProviderError("JPEG unavailable")
            return render_frame(0)

    monkeypatch.setattr("app.digitraffic.DigitrafficSnapshot", Snapshot)
    try:
        result = list(provider.discover("C14516", "C1451601"))
        assert len(result) == 1 and result[0][0]["id"] == "digitraffic-C1000201"
        assert seen == ["C10001", "C10002"]
        assert any("JPEG unavailable" in r["result"] for r in provider.discovery_diagnostics)
    finally:
        provider.http.close()


def test_dynamic_discovery_budget_and_no_synthetic_fallback(monkeypatch):
    provider = DigitrafficService()
    monkeypatch.setattr(
        provider,
        "camera_stations",
        lambda: [{"id": f"C{i:05d}", "available": True} for i in range(30)],
    )
    attempts = []
    monkeypatch.setattr(provider, "camera_presets", lambda station: attempts.append(station) or [])
    try:
        assert list(provider.discover(max_stations=3)) == []
        assert len(attempts) == 3
    finally:
        provider.http.close()


@pytest.mark.parametrize("width,height", [(320, 180), (960, 540)])
def test_normalized_snapshot_boxes_scale_on_the_same_frame(settings, width, height):
    import numpy as np

    from app.pipeline import Pipeline
    from app.storage import Store
    from app.tracking import Detection

    store = Store(settings.db_path)
    pipeline = Pipeline(settings, store)
    try:
        pipeline.mode = "SNAPSHOT"
        pipeline.config.zones = []
        image = np.zeros((height, width, 3), dtype=np.uint8)
        detection = Detection((0.1, 0.2, 0.4, 0.6), "car", 0.8)
        drawn = pipeline._draw(image, [], [detection])
        assert drawn[int(height * 0.4), int(width * 0.1)].any()
        assert drawn[int(height * 0.4), int(width * 0.4)].any()
        assert not drawn[int(height * 0.8), int(width * 0.8)].any()
    finally:
        pipeline.digitraffic.http.close()
        store.close()


def test_thumbnail_url_is_explicit_and_does_not_allow_arbitrary_queries():
    assert vetted_url(IMAGE + "?thumbnail=true") == IMAGE + "?thumbnail=true"
    with pytest.raises(ProviderError):
        vetted_url(IMAGE + "?thumbnail=true&other=secret")


def test_failed_known_real_selection_stops_demo_instead_of_showing_it(settings):
    from fastapi.testclient import TestClient

    from app.main import create_app

    settings.digitraffic_enabled = True
    with TestClient(create_app(settings)) as client:
        p = client.app.state.pipeline
        assert client.post("/api/cameras/demo/activate").status_code == 200
        camera = presets(feature())[0]
        p.digitraffic.resolved[camera["id"]] = camera
        settings.model_path = "missing-test-weights.pt"
        response = client.post(f"/api/cameras/{camera['id']}/activate")
        assert response.status_code == 409
        state = client.get("/api/system/status").json()
        assert state["camera_id"] == camera["id"] and state["state"] == "OFFLINE"
        assert state["ai_state"] != "active"
        assert state["visible_vehicles"] is None
        assert state["input_type"] == "not_opened" and state["latency_p50_ms"] is None
        assert client.get("/api/stream/frame.jpg?camera_id=demo").status_code == 409
        assert p.raw is None and p.annotated is None and not p.threads


def test_encoding_failure_cannot_publish_a_new_frame_identity(settings, monkeypatch):
    from app.pipeline import Pipeline
    from app.storage import Store

    store = Store(settings.db_path)
    pipeline = Pipeline(settings, store)
    pipeline.frame_id = "previous-frame"

    class Detector:
        name = "Mock detector for encoding failure regression"

        def detect(self, *args):
            pipeline.stop_event.set()
            return []

    monkeypatch.setattr("app.pipeline.SyntheticDetector", Detector)
    monkeypatch.setattr(cv2, "imencode", lambda *args: (False, None))
    pipeline.frames.put(
        (
            render_frame(0),
            time.monotonic(),
            datetime.now(UTC).isoformat(),
            1,
            None,
            "local receipt",
            None,
            None,
        )
    )
    try:
        pipeline._process()
        assert pipeline.frame_id == "previous-frame"
        assert pipeline.raw is None and pipeline.visible_vehicles is None
        assert pipeline.error is not None and pipeline.status()["ai_state"] != "active"
    finally:
        pipeline.digitraffic.http.close()
        store.close()
