"""Evidence-based small-person recovery without inferred identities or phantom counts."""

from types import SimpleNamespace

import numpy as np

from app.person_evidence import PersonEvidenceGate
from app.tracking import Detection, Tracker
from app.vision import YoloDetector


def person(confidence: float, x: float = 0.22) -> Detection:
    return Detection((x, 0.24, x + 0.12, 0.59), "person", confidence)


def test_weak_box_needs_two_model_observations_to_count():
    gate = PersonEvidenceGate()
    threshold = 0.35
    assert abs(PersonEvidenceGate.candidate_floor(threshold) - 0.23) < 0.00001
    assert gate.filter([person(0.24)], 1, threshold) == []
    observed = gate.filter([person(0.27, 0.225)], 1.5, threshold)
    assert len(observed) == 1 and observed[0].confidence == 0.27
    assert gate.weak_admitted == 1
    # Counts use the current model box, not a held prior-frame estimate.
    assert gate.filter([], 2, threshold) == []
    assert gate.weak_admitted == 0


def test_strong_person_is_counted_immediately_and_temporary_weak_recovery():
    gate = PersonEvidenceGate()
    assert len(gate.filter([person(0.78)], 1, 0.35)) == 1
    assert len(gate.filter([person(0.25)], 1.5, 0.35)) == 1
    assert gate.weak_admitted == 1


def test_weak_box_does_not_confirm_with_unrelated_neighbor_or_old_frame():
    gate = PersonEvidenceGate()
    assert gate.filter([person(0.25, 0.20)], 0, 0.35) == []
    assert gate.filter([person(0.25, 0.52)], 0.5, 0.35) == []
    assert gate.filter([person(0.26, 0.52)], 2.2, 0.35) == []
    assert len(gate.filter([person(0.26, 0.52)], 2.6, 0.35)) == 1


def test_candidate_memory_is_bounded_and_reset_on_source_change():
    gate = PersonEvidenceGate(capacity=5)
    many = [person(0.24, 0.03 * i) for i in range(25)]
    assert gate.filter(many, 0, 0.35) == []
    assert len(gate.candidates) == 5
    gate.reset()
    assert gate.candidates == []
    assert gate.filter([person(0.24)], 1, 0.35) == []


def test_held_track_is_not_returned_as_a_current_observation():
    tracker = Tracker()
    first = tracker.update([person(0.9)], 0)
    assert len(first) == 1
    assert tracker.update([], 0.5) == []
    # The last confirmed anonymous image position exists for a short visual
    # grace period, but it is not in the current observations or people count.
    assert len(tracker.tracks) == 1
    assert tracker.update([person(0.9)], 0.9)[0].id == first[0].id


def test_person_inference_requests_high_detail_while_vehicle_fixture_stays_standard(monkeypatch):
    import sys
    from types import ModuleType

    class FakeResults:
        pass

    fake_module = ModuleType("ultralytics.engine.results")
    fake_module.Results = FakeResults
    monkeypatch.setitem(sys.modules, "ultralytics.engine.results", fake_module)
    used = []

    def predict(*args, **kwargs):
        used.append((kwargs["imgsz"], kwargs["conf"], kwargs["classes"]))
        return [FakeResults()]

    detector = object.__new__(YoloDetector)
    detector.model = SimpleNamespace(predict=predict)
    detector.device = "cpu"
    detector.target = "person"
    detector.person_image_size = 960
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    detector._predict(frame, 0.23)
    detector.target = "vehicle"
    detector._predict(frame, 0.35)
    assert used == [(960, 0.23, [0]), (640, 0.35, [2, 3, 5, 7])]


def test_temporal_gate_never_invents_person_on_empty_frame():
    gate = PersonEvidenceGate()
    assert len(gate.filter([person(0.90)], 1, 0.35)) == 1
    assert gate.filter([], 1.5, 0.35) == []
    assert gate.filter([], 2, 0.35) == []


def test_detail_size_backs_off_when_several_predictions_are_slow(monkeypatch):
    from app import vision

    detector = object.__new__(YoloDetector)
    detector.device = "cpu"
    detector.target = "person"
    detector.person_image_size = 960
    detector._slow_detail_samples = 0
    detector._predict = lambda *_args: SimpleNamespace(boxes=None)
    sample_times = iter([value for i in range(5) for value in (float(i), i + 0.5)])
    monkeypatch.setattr(vision, "time", SimpleNamespace(perf_counter=lambda: next(sample_times)))
    for _ in range(5):
        assert detector.detect(np.zeros((4, 4, 3), dtype=np.uint8), 0.2) == []
    assert detector.person_image_size == 832


def test_admitted_person_can_be_weakly_redetected_after_one_missed_sample():
    gate = PersonEvidenceGate()
    assert len(gate.filter([person(0.88, 0.22)], 1.0, 0.35)) == 1
    assert gate.filter([], 1.5, 0.35) == []  # Miss never invents a current count.
    resumed = gate.filter([person(0.26, 0.222)], 2.0, 0.35)
    assert len(resumed) == 1 and resumed[0].confidence == 0.26


def test_unconfirmed_person_cannot_bridge_missing_samples_to_be_counted():
    gate = PersonEvidenceGate()
    assert gate.filter([person(0.24)], 1.0, 0.35) == []
    assert gate.filter([], 1.5, 0.35) == []
    assert gate.filter([person(0.27)], 2.0, 0.35) == []
    assert len(gate.filter([person(0.28)], 2.5, 0.35)) == 1
