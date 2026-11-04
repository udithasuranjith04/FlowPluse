"""Dependency-free anonymous image-plane track association."""

import math
import uuid
from collections import deque
from dataclasses import dataclass, field


def _box_overlap(
    a: tuple[float, float, float, float], b: tuple[float, float, float, float]
) -> float:
    x1, y1, x2, y2 = a
    xx1, yy1, xx2, yy2 = b
    intersection = max(0.0, min(x2, xx2) - max(x1, xx1)) * max(0.0, min(y2, yy2) - max(y1, yy1))
    total = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    total += max(0.0, xx2 - xx1) * max(0.0, yy2 - yy1)
    denominator = total - intersection
    return intersection / denominator if denominator > 0 else 0.0


@dataclass
class Detection:
    box: tuple[float, float, float, float]
    label: str
    confidence: float

    @property
    def anchor(self) -> tuple[float, float]:
        x1, _, x2, y2 = self.box
        return ((x1 + x2) / 2, y2)


@dataclass
class Track:
    id: str
    detection: Detection
    born: float
    seen: float
    history: deque = field(default_factory=lambda: deque(maxlen=120))

    def observe(self, detection: Detection, now: float) -> None:
        self.detection = detection
        self.seen = now
        self.history.append((now, *detection.anchor))

    @property
    def motion(self) -> float:
        if len(self.history) < 2:
            return 0.0
        last = self.history[-1]
        first = next((p for p in self.history if last[0] - p[0] <= 2.0), self.history[0])
        dt = last[0] - first[0]
        return (
            math.hypot(last[1] - first[1], last[2] - first[2]) / (dt * math.sqrt(2))
            if dt > 0
            else 0.0
        )


class Tracker:
    """Class-aware greedy spatial matching with velocity prediction and a short gap TTL."""

    def __init__(self, max_gap: float = 2.5):
        self.max_gap = max_gap
        self.reset()

    def reset(self) -> None:
        self.session = uuid.uuid4().hex[:8]
        self.counter = 0
        self.tracks: dict[str, Track] = {}

    def update(self, detections: list[Detection], now: float) -> list[Track]:
        self.tracks = {k: t for k, t in self.tracks.items() if now - t.seen <= self.max_gap}
        pairs = []
        for key, track in self.tracks.items():
            px, py = track.detection.anchor
            if len(track.history) >= 2:
                a, b = track.history[-2], track.history[-1]
                dt = b[0] - a[0]
                if dt > 0:
                    px += (b[1] - a[1]) / dt * (now - track.seen)
                    py += (b[2] - a[2]) / dt * (now - track.seen)
            for i, detection in enumerate(detections):
                distance = math.dist((px, py), detection.anchor)
                if track.detection.label == detection.label and distance < 0.12:
                    # Image overlap helps prefer the same individual when two
                    # anonymous people are close. No visual appearance, face,
                    # clothing, or identity embedding is used for matching.
                    overlap = _box_overlap(track.detection.box, detection.box)
                    pairs.append((distance + 0.035 * (1 - overlap), key, i))
        used_tracks: set[str] = set()
        used_detections: set[int] = set()
        current = []
        for _, key, index in sorted(pairs):
            if key not in used_tracks and index not in used_detections:
                track = self.tracks[key]
                track.observe(detections[index], now)
                used_tracks.add(key)
                used_detections.add(index)
                current.append(track)
        for index, detection in enumerate(detections):
            if index not in used_detections:
                self.counter += 1
                key = f"{self.session}:{self.counter}"
                track = Track(key, detection, now, now)
                track.observe(detection, now)
                self.tracks[key] = track
                current.append(track)
        return current
