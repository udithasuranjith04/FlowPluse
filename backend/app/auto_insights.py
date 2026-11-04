"""Automatic, bounded image-plane people insights, without spatial calibration.

These are observations about *pixels in a view*, not room occupancy, queues,
identified people, or physical doorway entries/exits. All state is in-memory.
"""

from collections import Counter, deque
from dataclasses import dataclass

from app.count_quality import SustainedCountPeak
from app.scene_discovery import SceneDiscovery
from app.tracking import Detection, Track


@dataclass
class CrossingState:
    side: int
    last_seen: float
    last_crossed: float = float("-inf")


class AutomaticInsights:
    """Session-only, no-configuration measurements from healthy camera frames.

    A stable vertical *image* midline is used for bidirectional image-crossing
    estimates. Camera motion invalidates the interpretation, so no physical
    entrances or exits are inferred or persisted as events.
    """

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.samples: deque[tuple[float, int, tuple[int, ...]]] = deque(maxlen=90)
        self.crossing_states: dict[str, CrossingState] = {}
        self.left_to_right = 0
        self.right_to_left = 0
        self.last_sample_at: float | None = None
        self.latest_track_durations: list[float] = []
        # Session-only aggregates. Counts never retain raw frames, track IDs, or identities.
        self.session_started_at: float | None = None
        self.session_samples = 0
        self.session_count_sum = 0
        self.session_peak = 0
        self.supported_count_peak = SustainedCountPeak()
        self.supported_guest_peak = SustainedCountPeak()
        self.session_busy_samples = 0
        self.session_minutes: deque[tuple[int, int, int]] = deque(maxlen=720)
        self.staff_only_region = "none"
        self.guest_area_visible: int | None = None
        self.guest_area_recent: deque[int] = deque(maxlen=90)
        self.guest_area_sum = 0
        self.guest_area_peak = 0
        self.scene_discovery = SceneDiscovery()

    def step(
        self,
        detections: list[Detection],
        tracks: list[Track],
        now: float,
        *,
        healthy: bool,
        monitoring: bool,
        staff_only_region: str = "none",
    ) -> None:
        if not healthy:
            # Do not bridge an unhealthy interval when asking for five nearby
            # healthy observations to support a high count.
            self.supported_count_peak.recent.clear()
            self.supported_guest_peak.recent.clear()
            self.crossing_states.clear()
            self.latest_track_durations = []
            self.guest_area_visible = None
            return
        if self.last_sample_at is not None and (
            now <= self.last_sample_at or now - self.last_sample_at > 3.0
        ):
            self.crossing_states.clear()
            if now <= self.last_sample_at:
                return
        self.last_sample_at = now
        # A camera position hint is not staff classification: count all people
        # and, separately, footpoints outside an operator-confirmed staff area.
        if staff_only_region != self.staff_only_region:
            # Never mix counts or session averages across different geometry.
            self.reset()
            self.last_sample_at = now
        self.staff_only_region = staff_only_region
        guest_count = 0
        grid = [0] * 9
        self.latest_track_durations = [
            max(0.0, now - track.born) for track in tracks if track.detection.label == "person"
        ]
        for detection in detections:
            if detection.label != "person":
                continue
            x, y = detection.anchor
            if staff_only_region != "none":
                in_staff_region = (
                    (staff_only_region == "left" and x < 0.5)
                    or (staff_only_region == "right" and x >= 0.5)
                    or (staff_only_region == "top" and y < 0.5)
                    or (staff_only_region == "bottom" and y >= 0.5)
                )
                if not in_staff_region:
                    guest_count += 1
            col = min(2, max(0, int(x * 3)))
            row = min(2, max(0, int(y * 3)))
            grid[row * 3 + col] += 1
        visible = sum(grid)
        self.guest_area_visible = guest_count if staff_only_region != "none" else None
        if staff_only_region != "none":
            self.guest_area_recent.append(guest_count)
        self.samples.append((now, visible, tuple(grid)))
        if monitoring:
            self.scene_discovery.step(detections, tracks, now)
        if monitoring:
            if self.session_started_at is None:
                self.session_started_at = now
            self.session_samples += 1
            self.session_count_sum += visible
            self.session_peak = max(self.session_peak, visible)
            self.supported_count_peak.add(visible, now)
            if staff_only_region != "none":
                self.guest_area_sum += guest_count
                self.guest_area_peak = max(self.guest_area_peak, guest_count)
                self.supported_guest_peak.add(guest_count, now)
            if visible >= 7:
                self.session_busy_samples += 1
            minute = int((now - self.session_started_at) // 60)
            if self.session_minutes and self.session_minutes[-1][0] == minute:
                bucket, total, n = self.session_minutes.pop()
                self.session_minutes.append((bucket, total + visible, n + 1))
            else:
                self.session_minutes.append((minute, visible, 1))
        if not monitoring:
            self.crossing_states.clear()
            return
        visible_ids = set()
        for track in tracks:
            if track.detection.label != "person" or now - track.born < 1.0:
                continue
            x, _ = track.detection.anchor
            side = -1 if x < 0.46 else 1 if x > 0.54 else 0
            if side == 0:
                continue
            visible_ids.add(track.id)
            previous = self.crossing_states.get(track.id)
            if previous is None:
                self.crossing_states[track.id] = CrossingState(side, now)
            else:
                # Observe a genuine track movement, not a new ID appearing on
                # the other side or a resurrected association after a gap.
                if (
                    previous.side != side
                    and now - previous.last_seen <= 2.0
                    and now - previous.last_crossed >= 2.0
                    and track.history
                    and len(track.history) >= 2
                    and max(p[1] for p in track.history) - min(p[1] for p in track.history) >= 0.08
                ):
                    if previous.side < 0:
                        self.left_to_right += 1
                    else:
                        self.right_to_left += 1
                    previous.last_crossed = now
                previous.side = side
                previous.last_seen = now
        self.crossing_states = {
            key: value
            for key, value in self.crossing_states.items()
            if key in visible_ids and now - value.last_seen <= 2.0
        }

    def snapshot(self) -> dict:
        counts = [count for _, count, _ in self.samples]
        sample_size = len(counts)
        durations = self.latest_track_durations
        if sample_size >= 24:
            previous = sum(counts[-24:-12]) / 12
            current = sum(counts[-12:]) / 12
            threshold = max(1.5, previous * 0.2)
            trend = (
                "rising"
                if current - previous > threshold
                else "falling"
                if previous - current > threshold
                else "steady"
            )
        else:
            trend = "warming_up"
        positions: Counter[int] = Counter()
        for _, _, cells in self.samples:
            positions.update({index: cell for index, cell in enumerate(cells) if cell})
        total = sum(positions.values())
        peak_index = positions.most_common(1)[0][0] if total and sample_size >= 10 else None
        sectors = (
            ("top left", "top center", "top right"),
            ("middle left", "center", "middle right"),
            ("bottom left", "bottom center", "bottom right"),
        )
        current_visible = counts[-1] if counts else None
        if current_visible is None:
            pace = "learning"
        elif current_visible >= 12:
            pace = "rush"
        elif current_visible >= 7:
            pace = "busy"
        elif current_visible >= 3:
            pace = "steady"
        else:
            pace = "quiet"
        return {
            "sample_count": sample_size,
            "average_visible": round(sum(counts) / sample_size, 1) if sample_size else None,
            "peak_visible": max(counts) if counts else None,
            "visible_trend": trend,
            "busiest_image_sector": (
                sectors[peak_index // 3][peak_index % 3] if peak_index is not None else None
            ),
            "sector_share": (
                round(positions[peak_index] / total, 2) if peak_index is not None else None
            ),
            "image_midline_crossings": {
                "left_to_right": self.left_to_right,
                "right_to_left": self.right_to_left,
            },
            "longest_visible_seconds": round(max(durations), 1) if durations else None,
            "average_track_age_seconds": round(sum(durations) / len(durations), 1)
            if durations
            else None,
            "active_lingerers": sum(duration >= 15 for duration in durations),
            "service_level": pace,
            "staff_only_region": self.staff_only_region,
            "guest_area_visible": self.guest_area_visible,
            "guest_area_recent": list(self.guest_area_recent),
            "scene_discovery": self.scene_discovery.snapshot(),
            "session_summary": {
                "processed_samples": self.session_samples,
                "average_visible": (
                    round(self.session_count_sum / self.session_samples, 1)
                    if self.session_samples
                    else None
                ),
                # Raw max is retained for debugging and backward-compatible
                # exports. The owner headline uses the sustained high instead.
                "peak_visible": self.session_peak if self.session_samples else None,
                "supported_peak_visible": self.supported_count_peak.supported_peak,
                "peak_possible_outlier": self.supported_count_peak.isolated_spike_possible,
                "peak_support_window": self.supported_count_peak.samples,
                "guest_area_average": (
                    round(self.guest_area_sum / self.session_samples, 1)
                    if self.session_samples and self.staff_only_region != "none"
                    else None
                ),
                "supported_guest_area_peak": (
                    self.supported_guest_peak.supported_peak
                    if self.staff_only_region != "none"
                    else None
                ),
                "guest_area_peak": (
                    self.guest_area_peak
                    if self.session_samples and self.staff_only_region != "none"
                    else None
                ),
                "busy_sample_percent": (
                    round(100 * self.session_busy_samples / self.session_samples)
                    if self.session_samples
                    else None
                ),
                "elapsed_seconds": (
                    round(self.last_sample_at - self.session_started_at)
                    if self.session_started_at is not None and self.last_sample_at is not None
                    else 0
                ),
                "minute_averages": [
                    {"minute": minute, "average": round(total / n, 1)}
                    for minute, total, n in self.session_minutes
                ],
            },
            "limitations": (
                "Image-plane estimates only; camera must be stationary. "
                "Midline crossings are NOT entrances/exits. "
                "Busiest sector is NOT a queue or physical density. "
                "Track-age values only describe currently visible anonymous tracks. "
                "Guest-area people may include staff, and customers may cross the staff area."
            ),
        }
