from app.quality import Continuity


def test_frozen_frames_are_rejected_before_temporal_rules():
    quality = Continuity()
    assert quality.update(b"same", 0, 0, 0, 2) == []
    assert quality.update(b"same", 2, 0, 0, 2) == []
    assert quality.update(b"same", 3, 0, 0, 2) == ["frozen_input"]
    assert quality.update(b"new", 3.5, 0.01, 0, 2) == []


def test_camera_cut_and_long_gap_invalidate_tracking_continuity():
    quality = Continuity()
    quality.update(b"first", 0, 0, 0, 2)
    assert quality.update(b"second", 0.5, 0.5, 0, 2) == ["camera_movement"]
    assert quality.update(b"third", 5, 0.01, 0, 2) == ["frame_gap"]


def test_configured_low_sampling_and_replay_loop():
    quality = Continuity()
    quality.update(b"a", 0, 0, 0, 0.5)
    assert quality.update(b"b", 2, 0, 0, 0.5) == []
    assert quality.update(b"c", 4, 0, 1, 0.5) == ["source_boundary"]
