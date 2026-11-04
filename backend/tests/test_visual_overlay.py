"""Display grace must never fabricate observations or survive stale inputs."""

from app.tracking import Detection, Tracker
from app.visual_overlay import build_visual_overlays


def person(x=0.2):
    return Detection((x, 0.15, x + 0.1, 0.55), "person", 0.92)


def test_one_missing_sample_is_dashed_and_not_counted():
    tracker = Tracker()
    first = tracker.update([person()], 10)
    assert build_visual_overlays(first, tracker.tracks, 10, allow_held=True) == [
        {"id": first[0].id, "box": list(person().box), "confidence": 0.92, "held": False}
    ]
    current = tracker.update([], 10.5)
    assert current == []  # Both current counts and zone rules see no detections.
    hints = build_visual_overlays(current, tracker.tracks, 10.5, allow_held=True)
    assert len(hints) == 1
    assert hints[0]["held"] is True
    assert hints[0]["held_age_seconds"] == 0.5
    assert hints[0]["id"] == first[0].id
    assert build_visual_overlays(current, tracker.tracks, 10.5, allow_held=False) == []


def test_visual_hint_expires_and_current_detection_replaces_it():
    tracker = Tracker()
    first = tracker.update([person()], 10)
    tracker.update([], 11.0)
    assert build_visual_overlays([], tracker.tracks, 11.0, allow_held=True) == []
    resumed = tracker.update([person(0.22)], 11.1)
    assert resumed[0].id == first[0].id
    visible = build_visual_overlays(resumed, tracker.tracks, 11.1, allow_held=True)
    assert len(visible) == 1 and visible[0]["held"] is False
    tracker.reset()
    assert build_visual_overlays([], tracker.tracks, 11.2, allow_held=True) == []


def test_visual_hint_is_bounded_and_person_only():
    tracker = Tracker()
    tracker.update([person(x=0.015 * i) for i in range(90)], 10)
    tracker.update([], 10.4)
    hints = build_visual_overlays([], tracker.tracks, 10.4, allow_held=True)
    assert len(hints) == 64
    assert all(hint["held"] for hint in hints)


def test_visual_hint_excludes_non_person_track():
    tracker = Tracker()
    observed = tracker.update([Detection((0.1, 0.2, 0.3, 0.5), "car", 0.95)], 3)
    assert len(build_visual_overlays(observed, tracker.tracks, 3, allow_held=True)) == 1
    assert tracker.update([], 3.5) == []
    assert build_visual_overlays([], tracker.tracks, 3.5, allow_held=True) == []
