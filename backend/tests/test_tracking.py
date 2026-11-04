from app.tracking import Detection, Tracker


def det(x=0.2, label="car"):
    return Detection((x, 0.3, x + 0.1, 0.4), label, 0.9)


def test_short_gap_matches_but_long_gap_gets_new_id():
    tracker = Tracker()
    original = tracker.update([det()], 0)[0].id
    assert tracker.update([], 0.5) == []
    assert tracker.update([det(0.21)], 1)[0].id == original
    assert tracker.update([det(0.21)], 5)[0].id != original


def test_reset_and_class_separation():
    tracker = Tracker()
    original = tracker.update([det()], 0)[0].id
    assert tracker.update([det(label="bus")], 0.5)[0].id != original
    tracker.reset()
    assert tracker.update([det()], 1)[0].id != original


def test_motion_is_normalized_image_plane():
    tracker = Tracker()
    tracker.update([det()], 0)
    track = tracker.update([det(0.22)], 1)[0]
    assert 0.01 < track.motion < 0.02
