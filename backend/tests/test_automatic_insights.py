"""Automatic image-plane signals without identity, manual geometry or persistence."""

from app.auto_insights import AutomaticInsights
from app.flow import FlowEngine
from app.schemas import Zone, ZoneConfig
from app.tracking import Detection, Track


def track(track_id: str, x: float, now: float, born: float = 0) -> Track:
    detection = Detection((x - 0.03, 0.4, x + 0.03, 0.8), "person", 0.92)
    t = Track(track_id, detection, born, now)
    t.observe(detection, now)
    return t


def test_auto_summary_requires_no_regions_and_resets():
    auto = AutomaticInsights()
    for tick in range(30):
        persons = [track(f"{tick}:{i}", 0.1, tick) for i in range(3)]
        auto.step(
            [t.detection for t in persons],
            persons,
            float(tick),
            healthy=True,
            monitoring=False,
        )
    report = auto.snapshot()
    assert report["sample_count"] == 30
    assert report["average_visible"] == 3
    assert report["peak_visible"] == 3
    assert report["visible_trend"] == "steady"
    assert report["busiest_image_sector"] == "bottom left"
    assert report["image_midline_crossings"] == {"left_to_right": 0, "right_to_left": 0}
    assert report["longest_visible_seconds"] == 29
    assert report["average_track_age_seconds"] == 29
    assert report["active_lingerers"] == 3
    assert report["service_level"] == "steady"
    auto.reset()
    assert auto.snapshot()["sample_count"] == 0
    assert auto.snapshot()["busiest_image_sector"] is None


def test_image_crossings_require_stable_track_and_monitoring():
    auto = AutomaticInsights()
    t = track("person:1", 0.25, 1.0)
    auto.step([t.detection], [t], 1, healthy=True, monitoring=True)
    t.observe(Detection((0.63, 0.4, 0.69, 0.8), "person", 0.92), 2)
    auto.step([t.detection], [t], 2, healthy=True, monitoring=True)
    assert auto.snapshot()["image_midline_crossings"]["left_to_right"] == 1
    auto.step([t.detection], [t], 2.5, healthy=True, monitoring=True)
    assert auto.snapshot()["image_midline_crossings"]["left_to_right"] == 1
    # Preview never counts movement across the centerline.
    t.observe(Detection((0.2, 0.4, 0.26, 0.8), "person", 0.92), 4)
    auto.step([t.detection], [t], 4, healthy=True, monitoring=False)
    assert auto.snapshot()["image_midline_crossings"]["right_to_left"] == 0


def test_unhealthy_input_cannot_bridge_crossing_and_is_not_sampled():
    auto = AutomaticInsights()
    t = track("p", 0.2, 1.0)
    auto.step([t.detection], [t], 1, healthy=True, monitoring=True)
    auto.step([], [], 1.5, healthy=False, monitoring=True)
    t.observe(Detection((0.7, 0.4, 0.76, 0.8), "person", 0.92), 2)
    auto.step([t.detection], [t], 2, healthy=True, monitoring=True)
    assert auto.snapshot()["image_midline_crossings"]["left_to_right"] == 0
    assert auto.snapshot()["sample_count"] == 2


def test_full_frame_counts_but_never_emits_dwell_or_queue():
    zone = Zone(
        id="quick-whole-frame",
        name="Full frame",
        points=[(0.01, 0.01), (0.99, 0.01), (0.99, 0.99), (0.01, 0.99)],
    )
    engine = FlowEngine("local-camera-1", ZoneConfig(zones=[zone]), "LIVE", "yolo11n")
    people = [track(f"p{i}", 0.2 + i * 0.1, 3.0) for i in range(3)]
    for instant in (3, 20, 60):
        assert engine.step(people, instant) == []
    assert engine.zone_counts["quick-whole-frame"] == 3
    assert engine.debug[0]["queue_state"] == "count_only"


def test_auto_summary_exposes_only_aggregate_lingering_metrics():
    auto = AutomaticInsights()
    guests = [
        track("a", 0.2, 20.0, born=0.0),
        track("b", 0.4, 20.0, born=10.0),
        track("c", 0.6, 20.0, born=18.0),
    ]
    auto.step([t.detection for t in guests], guests, 20.0, healthy=True, monitoring=False)
    report = auto.snapshot()
    assert report["longest_visible_seconds"] == 20
    assert report["average_track_age_seconds"] == 10.7
    assert report["active_lingerers"] == 1
    assert report["service_level"] == "steady"


def test_automatic_status_does_not_expose_tracks_or_video(client):
    pipeline = client.app.state.pipeline
    pipeline.camera_id = "local-camera-1"
    pipeline.settings.detection_target = "person"
    pipeline.auto_insights.step(
        [track("private-id", 0.2, 2).detection],
        [],
        2,
        healthy=True,
        monitoring=False,
    )
    report = client.get("/api/system/status").json()["automatic_insights"]
    assert report["sample_count"] == 1
    assert "private-id" not in str(report)
    assert "frame" not in report
    pipeline.stop()
    assert client.get("/api/system/status").json()["automatic_insights"]["sample_count"] == 0


def test_shift_summary_uses_monitoring_frames_only_and_resets():
    auto = AutomaticInsights()
    preview = [track("preview-guest", 0.3, 1, born=0)]
    auto.step([preview[0].detection], preview, 1.0, healthy=True, monitoring=False)
    assert auto.snapshot()["session_summary"]["processed_samples"] == 0
    for index, visible in enumerate((2, 7, 8, 1)):
        guests = [track(f"guest-{index}-{i}", 0.2, 10 + index) for i in range(visible)]
        auto.step(
            [guest.detection for guest in guests],
            guests,
            10.0 + index,
            healthy=True,
            monitoring=True,
        )
    summary = auto.snapshot()["session_summary"]
    assert summary["processed_samples"] == 4
    assert summary["average_visible"] == 4.5
    assert summary["peak_visible"] == 8
    assert summary["busy_sample_percent"] == 50
    assert summary["elapsed_seconds"] == 3
    assert summary["minute_averages"] == [{"minute": 0, "average": 4.5}]
    assert "guest-0-" not in str(summary)
    auto.reset()
    assert auto.snapshot()["session_summary"]["processed_samples"] == 0


def test_shift_summary_excludes_unhealthy_frames():
    auto = AutomaticInsights()
    guests = [track("guest", 0.3, 10)]
    auto.step([guests[0].detection], guests, 10, healthy=True, monitoring=True)
    auto.step([], [], 11, healthy=False, monitoring=True)
    assert auto.snapshot()["session_summary"]["processed_samples"] == 1


def test_unconfirmed_starter_waiting_template_never_creates_false_service_alerts():
    zone = Zone(
        id="quick-waiting-area",
        name="Starter waiting area · adjust location",
        points=[(0.2, 0.2), (0.8, 0.2), (0.8, 0.9), (0.2, 0.9)],
    )
    engine = FlowEngine("local-camera-1", ZoneConfig(zones=[zone]), "LIVE", "yolo11n")
    guests = [track(f"p{i}", 0.3 + i * 0.1, 2.0) for i in range(3)]
    for instant in (2.0, 20.0, 60.0):
        assert engine.step(guests, instant) == []
    assert engine.zone_counts["quick-waiting-area"] == 3
    assert engine.debug[0]["queue_state"] == "template_unconfirmed"


def test_guest_facing_counts_are_geometry_only_and_keep_full_camera_count():
    auto = AutomaticInsights()
    # Footpoints: x=.2 left, x=.8 right. These could be staff OR guests.
    visible = [track("left", 0.2, 10), track("right", 0.8, 10)]
    auto.step(
        [t.detection for t in visible],
        visible,
        10,
        healthy=True,
        monitoring=True,
        staff_only_region="left",
    )
    result = auto.snapshot()
    assert result["sample_count"] == 1
    assert result["average_visible"] == 2
    assert result["guest_area_visible"] == 1
    assert result["guest_area_recent"] == [1]
    assert result["session_summary"]["guest_area_average"] == 1
    assert result["session_summary"]["guest_area_peak"] == 1
    assert "left" not in str(result["session_summary"])
    assert "right" not in str(result["session_summary"])
    auto.reset()
    assert auto.snapshot()["guest_area_visible"] is None
    assert auto.snapshot()["session_summary"]["guest_area_average"] is None


def test_guest_facing_top_region_uses_footpoints_and_preview_not_shift():
    auto = AutomaticInsights()
    upper = Track("person-upper", Detection((0.1, 0.1, 0.3, 0.2), "person", 0.9), 0, 1)
    lower = Track("person-lower", Detection((0.6, 0.5, 0.8, 0.9), "person", 0.9), 0, 1)
    for item in (upper, lower):
        item.observe(item.detection, 1)
    auto.step(
        [upper.detection, lower.detection],
        [upper, lower],
        1,
        healthy=True,
        monitoring=False,
        staff_only_region="top",
    )
    result = auto.snapshot()
    assert result["guest_area_visible"] == 1
    assert result["session_summary"]["processed_samples"] == 0
    auto.step([], [], 2, healthy=False, monitoring=True, staff_only_region="top")
    assert auto.snapshot()["guest_area_visible"] is None
    assert auto.snapshot()["session_summary"]["processed_samples"] == 0


def test_changing_staff_region_never_mixes_shift_metrics():
    auto = AutomaticInsights()
    people = [track("one", 0.2, 1), track("two", 0.8, 1)]
    for instant, area in [(1.0, "none"), (2.0, "none"), (3.0, "left")]:
        auto.step(
            [person.detection for person in people],
            people,
            instant,
            healthy=True,
            monitoring=True,
            staff_only_region=area,
        )
    result = auto.snapshot()
    assert result["staff_only_region"] == "left"
    assert result["session_summary"]["processed_samples"] == 1
    assert result["guest_area_visible"] == 1
    assert result["session_summary"]["guest_area_average"] == 1
