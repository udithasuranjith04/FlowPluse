"""Automatic, anonymous image-plane activity regions for an authorized café view.

Presence and movement are scene measurements, NOT person roles or detected
semantic objects. No frames, track identifiers, clothing, identity or faces are kept.
"""

from collections import deque
from dataclasses import dataclass

from app.tracking import Detection, Track

COLS = 6
ROWS = 4
CELLS = COLS * ROWS
MAX_FRAMES = 360  # Up to ~3 minutes at the default 2 processed FPS.


@dataclass(frozen=True)
class SceneSample:
    at: float
    presence: tuple[int, ...]
    stationary: tuple[int, ...]
    moving: tuple[int, ...]


def cell_at(x: float, y: float) -> int:
    """Clamp normalized person footpoints to a deterministic 6 x 4 grid."""
    col = max(0, min(COLS - 1, int(x * COLS)))
    row = max(0, min(ROWS - 1, int(y * ROWS)))
    return row * COLS + col


class SceneDiscovery:
    """Data-driven location hotspots, with no guessed staff/customer labels."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.frames: deque[SceneSample] = deque(maxlen=MAX_FRAMES)
        self.last_frame_counts = [0] * CELLS

    def step(self, detections: list[Detection], tracks: list[Track], now: float) -> None:
        presence = [0] * CELLS
        stationary = [0] * CELLS
        moving = [0] * CELLS
        for detection in detections:
            if detection.label == "person":
                presence[cell_at(*detection.anchor)] += 1
        for track in tracks:
            if track.detection.label != "person" or len(track.history) < 3:
                continue
            cell = cell_at(*track.detection.anchor)
            age = max(0.0, now - track.born)
            if age >= 8.0 and track.motion < 0.008:
                stationary[cell] += 1
            elif age >= 1.0 and track.motion >= 0.02:
                moving[cell] += 1
        self.last_frame_counts = presence
        self.frames.append(SceneSample(now, tuple(presence), tuple(stationary), tuple(moving)))

    def snapshot(self) -> dict:
        n = len(self.frames)
        span = self.frames[-1].at - self.frames[0].at if n > 1 else 0.0
        total_presence = [0] * CELLS
        presence_frames = [0] * CELLS
        slow = [0] * CELLS
        movement = [0] * CELLS
        occupancy_episodes = [0] * CELLS
        previous_present = [False] * CELLS
        for sample in self.frames:
            for cell, count in enumerate(sample.presence):
                present = count > 0
                if present and not previous_present[cell]:
                    occupancy_episodes[cell] += 1
                previous_present[cell] = present
                total_presence[cell] += count
                presence_frames[cell] += int(present)
                slow[cell] += sample.stationary[cell]
                movement[cell] += sample.moving[cell]
        all_presence = sum(total_presence)
        ready = n >= 36 and span >= 15.0 and all_presence >= 30
        hotspots: list[dict] = []
        if ready:
            candidates = sorted(
                range(CELLS),
                key=lambda cell: (total_presence[cell], presence_frames[cell]),
                reverse=True,
            )
            selected: list[int] = []
            for cell in candidates:
                if len(selected) == 3:
                    break
                row, col = divmod(cell, COLS)
                if total_presence[cell] < 10 or presence_frames[cell] < 6:
                    continue
                # Adjacent hot tiles usually describe the same cluster; show
                # different parts of the scene rather than 3 identical cards.
                if any(
                    abs(row - other // COLS) <= 1 and abs(col - other % COLS) <= 1
                    for other in selected
                ):
                    continue
                selected.append(cell)
                if slow[cell] >= 6 and slow[cell] > movement[cell] * 1.3:
                    pattern = "longer_stays"
                elif movement[cell] >= 6 and movement[cell] > slow[cell] * 1.3:
                    pattern = "movement"
                else:
                    pattern = "frequent_presence"
                # Evidence strength means repeatability in this recent sample;
                # it is NOT probability of finding a staff/guest area.
                evidence = "strong" if presence_frames[cell] >= max(18, n * 0.18) else "developing"
                horizontal = (
                    "far left",
                    "left",
                    "center-left",
                    "center-right",
                    "right",
                    "far right",
                )
                vertical = ("Top", "Upper middle", "Lower middle", "Bottom")
                hotspots.append(
                    {
                        "id": f"scene-{row}-{col}",
                        "bounds": [
                            round(col / COLS, 4),
                            round(row / ROWS, 4),
                            round((col + 1) / COLS, 4),
                            round((row + 1) / ROWS, 4),
                        ],
                        "location": f"{vertical[row]} {horizontal[col]}",
                        "pattern": pattern,
                        "evidence": evidence,
                        "frames_with_people": presence_frames[cell],
                        "visible_now": self.last_frame_counts[cell],
                        "presence_share": round(total_presence[cell] / all_presence, 2),
                        "observed_seconds": round(span * presence_frames[cell] / n, 1),
                        "presence_percent": round(100 * presence_frames[cell] / n),
                        # Separate visible occupancy episodes, NOT individual visits.
                        # One seated person can produce hundreds of occupied frames.
                        "occupancy_episodes": occupancy_episodes[cell],
                    }
                )
        return {
            "state": "ready" if hotspots else "learning",
            "sampled_frames": n,
            "window_seconds": round(span, 1),
            "hotspots": hotspots,
            "disclaimer": (
                "Automatically learned image locations and anonymous motion patterns. "
                "Not staff/customer recognition, detected counters, queues, tables, "
                "actual waiting time or employee behavior. Episodes describe a region "
                "becoming occupied after being empty, not unique people or visits. "
                "Camera must remain fixed."
            ),
        }
