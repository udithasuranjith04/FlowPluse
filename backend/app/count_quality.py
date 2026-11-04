"""Honest, anonymous count reliability summaries from consecutive frames.

An isolated high detection count should not be the primary owner-facing shift
peak. This class keeps the raw maximum intact, but separately reports the
highest median across five consecutive healthy monitoring samples. It does not
infer occupancy, identify people, or manufacture missing detections.
"""

from collections import deque
from statistics import median


class SustainedCountPeak:
    """Small rolling window; retains no frames, tracks or individual labels."""

    def __init__(self, samples: int = 5, max_gap_seconds: float = 2.5):
        if samples < 3 or samples % 2 != 1:
            raise ValueError("The support window must be odd and at least three")
        self.samples = samples
        self.max_gap_seconds = max_gap_seconds
        self.recent: deque[tuple[float, int]] = deque(maxlen=samples)
        self.raw_peak = 0
        self.supported_peak: int | None = None
        self.total = 0

    def add(self, count: int, timestamp: float) -> None:
        if count < 0:
            raise ValueError("The current-frame people count cannot be negative")
        if self.recent and (
            timestamp <= self.recent[-1][0] or timestamp - self.recent[-1][0] > self.max_gap_seconds
        ):
            self.recent.clear()
        self.recent.append((timestamp, count))
        self.raw_peak = max(self.raw_peak, count)
        self.total += 1
        if len(self.recent) == self.samples:
            # A median of five has >=3 supporting samples, but is still only
            # a camera-view estimate, not a certified headcount.
            candidate = int(median(item[1] for item in self.recent))
            self.supported_peak = (
                candidate if self.supported_peak is None else max(self.supported_peak, candidate)
            )

    @property
    def isolated_spike_possible(self) -> bool:
        return self.supported_peak is not None and self.raw_peak - self.supported_peak >= max(
            3, self.supported_peak // 2
        )
