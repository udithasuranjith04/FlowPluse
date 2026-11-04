"""Isolated peaks stay visible in diagnostics but not owner headline counts."""

from app.auto_insights import AutomaticInsights
from app.count_quality import SustainedCountPeak
from app.tracking import Detection


def test_spike_does_not_become_sustained_high():
    peak = SustainedCountPeak()
    for index, count in enumerate([5, 5, 19, 5, 5]):
        peak.add(count, index * 0.5)
    assert peak.raw_peak == 19
    assert peak.supported_peak == 5
    assert peak.isolated_spike_possible


def test_busy_period_with_support_is_reported():
    peak = SustainedCountPeak()
    for index, count in enumerate([3, 6, 8, 8, 9, 10, 8]):
        peak.add(count, index * 0.5)
    assert peak.supported_peak == 8
    assert peak.raw_peak == 10
    assert not peak.isolated_spike_possible


def test_long_gap_cannot_be_used_as_consecutive_evidence():
    peak = SustainedCountPeak()
    for index, count in enumerate([2, 2, 2, 2, 2]):
        peak.add(count, index * 0.5)
    peak.add(18, 20)
    assert peak.supported_peak == 2
    assert peak.raw_peak == 18
    assert peak.isolated_spike_possible


def test_short_shift_shows_learning_for_sustained_peak():
    peak = SustainedCountPeak()
    for index, count in enumerate([2, 7, 8, 1]):
        peak.add(count, float(index))
    assert peak.supported_peak is None
    assert peak.raw_peak == 8


def test_session_summary_keeps_raw_peak_and_reports_supported_peak():
    auto = AutomaticInsights()
    for index, count in enumerate([4, 5, 18, 5, 4]):
        people = [
            Detection((0.01 + i * 0.001, 0.1, 0.012 + i * 0.001, 0.5), "person", 0.95)
            for i in range(count)
        ]
        auto.step(people, [], 10 + index * 0.5, healthy=True, monitoring=True)
    summary = auto.snapshot()["session_summary"]
    assert summary["peak_visible"] == 18
    assert summary["supported_peak_visible"] == 5
    assert summary["peak_possible_outlier"] is True
    assert summary["peak_support_window"] == 5
    auto.reset()
    assert auto.snapshot()["session_summary"]["supported_peak_visible"] is None


def test_unhealthy_sample_breaks_peak_support_window():
    auto = AutomaticInsights()
    for index in range(3):
        boxes = [Detection((0.01, 0.1, 0.1, 0.5), "person", 0.91)] * 9
        auto.step(boxes, [], float(index) / 2, healthy=True, monitoring=True)
    auto.step([], [], 1.25, healthy=False, monitoring=True)
    for index in range(2):
        boxes = [Detection((0.01, 0.1, 0.1, 0.5), "person", 0.91)] * 9
        auto.step(boxes, [], 1.5 + index / 2, healthy=True, monitoring=True)
    summary = auto.snapshot()["session_summary"]
    assert summary["peak_visible"] == 9
    assert summary["supported_peak_visible"] is None
