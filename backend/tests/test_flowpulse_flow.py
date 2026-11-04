"""Deterministic tests for image-plane people-flow rules, not real-world accuracy claims."""

import pytest
from pydantic import ValidationError

from app.flow import FlowEngine
from app.schemas import FlowLine, RuleConfig, Zone, ZoneConfig
from app.tracking import Detection, Track


def person(ident: str, x: float, y: float, now: float, born: float = 0) -> Track:
    detection = Detection((x - 0.025, y - 0.12, x + 0.025, y), "person", 0.91)
    track = Track(ident, detection, born, now)
    track.observe(detection, now)
    return track


def config() -> ZoneConfig:
    return ZoneConfig(
        zones=[
            Zone(
                id="waiting",
                name="Waiting area",
                points=[(0.1, 0.1), (0.9, 0.1), (0.9, 0.9), (0.1, 0.9)],
            )
        ],
        lines=[FlowLine(id="door", name="Door", points=((0.1, 0.5), (0.9, 0.5)))],
        rules=RuleConfig(
            min_track_age=1,
            flow_dwell_seconds=2,
            flow_queue_seconds=2,
            flow_queue_people=3,
            flow_slow_fraction=0.7,
            flow_crossing_margin=0.01,
            flow_crossing_cooldown=1,
        ),
    )


def test_two_point_line_validation():
    with pytest.raises(ValidationError):
        FlowLine(id="bad", name="Bad", points=((0.1, 0.1), (0.1, 0.1)))
    with pytest.raises(ValidationError):
        FlowLine(id="bad", name="Bad", points=((-0.1, 0.5), (0.9, 0.5)))
    with pytest.raises(ValidationError):
        ZoneConfig(
            lines=[
                FlowLine(id="dupe", name="A", points=((0, 0), (1, 0))),
                FlowLine(id="dupe", name="B", points=((0, 0), (1, 0))),
            ]
        )


def test_line_crossings_need_confirmed_sides_and_track_maturity():
    engine = FlowEngine("iphone", config(), "LIVE", "YOLO")
    assert engine.step([person("t1", 0.5, 0.3, 0)], 0) == []
    assert engine.entries == 0  # immature tracks cannot count
    engine.step([person("t1", 0.5, 0.3, 2)], 2)
    engine.step([person("t1", 0.5, 0.5, 2.5)], 2.5)  # in hysteresis band
    assert engine.entries == 0
    engine.step([person("t1", 0.5, 0.7, 3)], 3)
    assert (engine.entries, engine.exits) == (1, 0)
    engine.step([person("t1", 0.5, 0.75, 3.5)], 3.5)
    assert engine.entries == 1  # no double count while on the same side
    engine.step([person("t1", 0.5, 0.3, 5)], 5)
    assert (engine.entries, engine.exits) == (1, 1)


def test_dwell_and_possible_queue_are_separate_observations():
    engine = FlowEngine("iphone", config(), "LIVE", "YOLO")
    tracks = [person(f"p{i}", 0.25 + i * 0.1, 0.6, 2) for i in range(3)]
    assert engine.step(tracks, 2) == []
    assert engine.zone_counts == {"waiting": 3}
    changes = engine.step([person(f"p{i}", 0.25 + i * 0.1, 0.6, 5) for i in range(3)], 5)
    kinds = {change["type"] for change in changes}
    assert kinds == {"extended_dwell", "possible_queue_buildup"}
    assert sum(change["type"] == "extended_dwell" for change in changes) == 3
    assert all(change["quality_flags"] for change in changes)
    changes = engine.step([], 6)
    assert all(change["state"] == "resolved" for change in changes)
    assert engine.zone_counts == {"waiting": 0}


def test_preview_disconnection_and_snapshot_never_emit_flow_events():
    engine = FlowEngine("iphone", config(), "LIVE", "YOLO")
    track = person("session:one", 0.5, 0.4, 5)
    engine.step([track], 5)
    engine.step([person("session:one", 0.5, 0.7, 6)], 6)
    assert engine.entries == 1
    engine.step([], 8, quality=False)
    assert engine.entries == engine.exits == 0
    assert engine.line_states == {}
    snapshot = FlowEngine("public", config(), "SNAPSHOT", "YOLO")
    for n in range(30):
        assert snapshot.step([person("still", 0.5, 0.6, n + 5)], n + 5) == []
    assert snapshot.entries == 0


def test_ignore_zone_excludes_detections():
    settings = config()
    settings.zones.append(
        Zone(
            id="exclude",
            name="Excluded",
            kind="ignore",
            points=[(0.3, 0.3), (0.7, 0.3), (0.7, 0.8), (0.3, 0.8)],
        )
    )
    engine = FlowEngine("iphone", settings, "LIVE", "YOLO")
    engine.step([person("ignored", 0.5, 0.4, 2)], 2)
    engine.step([person("ignored", 0.5, 0.7, 4)], 4)
    assert engine.zone_counts == {"waiting": 0}
    assert engine.entries == 0
