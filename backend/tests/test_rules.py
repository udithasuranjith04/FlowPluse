from app.rules import RuleEngine
from app.schemas import Zone, ZoneConfig
from app.tracking import Detection, Tracker


def detection(x=0.2, y=0.4, width=0.1):
    return Detection((x, y, x + width, y + 0.15), "car", 0.9)


def engine(config):
    return RuleEngine("demo", config, "REPLAY", "test detector")


def test_stop_lifecycle_dedupe_review_independent_and_cooldown(fast_config):
    rule, tracker = engine(fast_config), Tracker()
    changes = []
    for t in range(8):
        changes += rule.step(tracker.update([detection()], t), t)
    assert len({e["id"] for e in changes}) == 1
    assert changes[-1]["state"] == "active"
    resolved = rule.step(tracker.update([detection(0.27)], 8), 8)
    assert resolved[0]["state"] == "resolved"
    assert resolved[0]["ended_at"]
    assert len(rule.active) == 0
    for t in range(9, 13):
        assert not rule.step(tracker.update([detection(0.27)], t), t)


def test_movement_short_pause_no_zone_and_stale_suppressed(fast_config):
    rule, tracker = engine(fast_config), Tracker()
    for t in range(15):
        assert not rule.step(tracker.update([detection(0.05 + t * 0.025)], t), t)
    rule = engine(ZoneConfig())
    for t in range(10):
        assert not rule.step(tracker.update([detection()], t + 20), t + 20)
    rule = engine(fast_config)
    for t in range(10):
        assert not rule.step(tracker.update([detection()], t + 40), t + 40, quality=False)


def test_snapshot_never_emits_and_ignore_zone_wins(fast_config):
    tracker = Tracker()
    rule = RuleEngine("snap", fast_config, "SNAPSHOT", "test")
    for t in range(10):
        assert not rule.step(tracker.update([detection()], t), t)
    fast_config.zones.append(
        Zone(id="ignore", name="Ignore", kind="ignore", points=[(0, 0), (1, 0), (1, 1), (0, 1)])
    )
    rule = engine(fast_config)
    for t in range(10, 20):
        assert not rule.step(tracker.update([detection()], t), t)


def test_monitored_indoor_scene_with_no_vehicle_detections_never_emits(fast_config):
    rule = RuleEngine("owned-camera", fast_config, "LIVE", "test detector")
    for t in range(120):
        assert rule.step([], t) == []
    assert not rule.active and not rule.candidates


def test_traffic_wide_stop_does_not_flag_individual_vehicle(fast_config):
    rule, tracker = engine(fast_config), Tracker()
    for t in range(12):
        events = rule.step(tracker.update([detection(x) for x in (0.1, 0.4, 0.7)], t), t)
        assert not any(e["type"] == "potential_stopped_vehicle" for e in events)
    assert rule.debug[0]["general_stop_suppression"]


def test_congestion_requires_warmup_sustained_change_and_clears(fast_config):
    rule, tracker = engine(fast_config), Tracker()
    for t in range(9):
        events = rule.step(tracker.update([detection(0.1 + t * 0.03)], t), t)
        assert not events
    all_events = []
    for t in range(9, 15):
        all_events += rule.step(
            tracker.update([detection(x, width=0.25) for x in (0.05, 0.35, 0.65)], t), t
        )
    queues = [e for e in all_events if e["type"] == "congestion_buildup"]
    assert queues and len({e["id"] for e in queues}) == 1
    assert queues[0]["features"]["baseline"]["motion"] > 0
    resolved = rule.step([], 16)
    assert any(e["type"] == "congestion_buildup" and e["state"] == "resolved" for e in resolved)


def test_brief_queue_spike_does_not_emit(fast_config):
    rule, tracker = engine(fast_config), Tracker()
    for t in range(9):
        rule.step(tracker.update([detection(0.1 + t * 0.03)], t), t)
    assert not rule.step(
        tracker.update([detection(x, width=0.25) for x in (0.05, 0.35, 0.65)], 9), 9
    )
    assert not rule.step([], 10)
