"""Scene patterns are aggregate observations, not inferred employee identities."""

from app.auto_insights import AutomaticInsights
from app.scene_discovery import SceneDiscovery, cell_at
from app.tracking import Detection, Track


def person(x: float, y: float = 0.6) -> Detection:
    return Detection((x - 0.015, y - 0.3, x + 0.015, y), "person", 0.9)


def test_scene_discovery_starts_learning_and_never_uses_preview():
    engine = AutomaticInsights()
    track = Track("anonymous-should-not-leak", person(0.3), 0, 0)
    for tick in range(45):
        track.observe(person(0.3), float(tick))
        engine.step([track.detection], [track], float(tick), healthy=True, monitoring=False)
    report = engine.snapshot()["scene_discovery"]
    assert report["state"] == "learning"
    assert report["sampled_frames"] == 0
    assert report["hotspots"] == []


def test_scene_discovery_recovers_stay_hotspot_from_healthy_monitoring():
    engine = SceneDiscovery()
    track = Track("private-track-key", person(0.3), 0.0, 0.0)
    for tick in range(50):
        track.observe(person(0.3), float(tick))
        engine.step([track.detection], [track], float(tick))
    result = engine.snapshot()
    assert result["state"] == "ready"
    assert result["sampled_frames"] == 50
    assert len(result["hotspots"]) == 1
    hotspot = result["hotspots"][0]
    assert hotspot["pattern"] == "longer_stays"
    assert hotspot["visible_now"] == 1
    assert hotspot["evidence"] == "strong"
    assert hotspot["occupancy_episodes"] == 1  # One person, not 50 new visits
    assert hotspot["observed_seconds"] >= 40
    assert hotspot["presence_percent"] == 100
    assert "private-track-key" not in str(result)
    assert "customer" not in hotspot
    engine.reset()
    assert engine.snapshot()["state"] == "learning"
    assert engine.snapshot()["hotspots"] == []


def test_scene_discovery_only_counts_people_and_clamps_edges():
    discovery = SceneDiscovery()
    assert cell_at(-1, -1) == 0
    assert cell_at(1, 1) == 23
    assert cell_at(0.5, 0.5) == 15
    dog = Detection((0.1, 0.1, 0.3, 0.5), "dog", 0.98)
    discovery.step([dog], [], 1.0)
    assert discovery.snapshot()["state"] == "learning"
    assert discovery.snapshot()["hotspots"] == []


def test_scene_discovery_unhealthy_frames_do_not_inflate_counts():
    engine = AutomaticInsights()
    track = Track("any", person(0.3), 0.0, 0.0)
    track.observe(person(0.3), 1.0)
    engine.step([track.detection], [track], 1.0, healthy=True, monitoring=True)
    engine.step([track.detection], [track], 2.0, healthy=False, monitoring=True)
    assert engine.snapshot()["scene_discovery"]["sampled_frames"] == 1


def test_multiple_occupancy_periods_are_not_called_person_visits():
    scene = SceneDiscovery()
    for second in range(60):
        present = second < 25 or second >= 30
        scene.step([person(0.35)] if present else [], [], float(second))
    result = scene.snapshot()
    assert result["state"] == "ready"
    hotspot = result["hotspots"][0]
    assert hotspot["occupancy_episodes"] == 2
    assert hotspot["frames_with_people"] == 55
    assert "visit" not in str(hotspot)


def test_scene_discovery_restarts_after_gap_or_clock_regression():
    scene = SceneDiscovery()
    for second in range(40):
        scene.step([person(0.35)], [], float(second))
    assert scene.snapshot()["state"] == "ready"
    scene.step([person(0.35)], [], 60.0)  # No bridging two separate camera periods.
    assert scene.snapshot()["state"] == "learning"
    assert scene.snapshot()["sampled_frames"] == 1
    scene.step([person(0.35)], [], 59.0)  # Stale/out-of-order sample.
    assert scene.snapshot()["sampled_frames"] == 1
    assert scene.snapshot()["state"] == "learning"


def test_unhealthy_sample_suspends_hotspots_until_fresh_learning():
    engine = AutomaticInsights()
    track = Track("ephemeral", person(0.35), 0, 0)
    for second in range(40):
        track.observe(person(0.35), float(second))
        engine.step([track.detection], [track], float(second), healthy=True, monitoring=True)
    assert engine.snapshot()["scene_discovery"]["state"] == "ready"
    engine.step([], [], 40.0, healthy=False, monitoring=True)
    report = engine.snapshot()["scene_discovery"]
    assert report["state"] == "learning"
    assert report["hotspots"] == []
    engine.step([track.detection], [track], 41.0, healthy=True, monitoring=True)
    assert engine.snapshot()["scene_discovery"]["sampled_frames"] == 1
