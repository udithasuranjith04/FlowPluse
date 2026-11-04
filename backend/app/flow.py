"""Privacy-preserving, session-only people flow measurements.

Counts and event candidates are derived from anonymous track footpoints. No image,
face template, or cross-session identity is retained by this module.
"""

import math
import statistics
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from shapely.geometry import Point, Polygon

from app.rules import utc_now
from app.schemas import FlowLine, ZoneConfig
from app.tracking import Track


def side(line: FlowLine, point: tuple[float, float]) -> float:
    """Normalized signed distance to the directed counting line (A to B)."""
    (ax, ay), (bx, by) = line.points
    length = math.hypot(bx - ax, by - ay)
    return ((bx - ax) * (point[1] - ay) - (by - ay) * (point[0] - ax)) / length


def inside_segment(line: FlowLine, point: tuple[float, float]) -> bool:
    (ax, ay), (bx, by) = line.points
    vx, vy = bx - ax, by - ay
    fraction = ((point[0] - ax) * vx + (point[1] - ay) * vy) / (vx * vx + vy * vy)
    return 0 <= fraction <= 1


@dataclass
class LineTrack:
    side: int
    last_counted: float = float("-inf")


class FlowEngine:
    """People flow rule engine, compatible with Pipeline's observation persistence.

    Crossing directions are defined by the user's ordered line endpoints:
    negative to positive = entry, positive to negative = exit.
    """

    def __init__(self, camera_id: str, config: ZoneConfig, mode: str, model: str):
        self.camera_id, self.config, self.mode, self.model = camera_id, config, mode, model
        self.active: dict[str, dict] = {}
        self.candidates: dict[str, float] = {}
        self.cooldowns: dict[str, float] = {}
        self.line_states: dict[tuple[str, str], LineTrack] = {}
        self.entries = 0
        self.exits = 0
        self.zone_counts: dict[str, int] = {}
        self.debug: list[dict] = []

    def reset(self, reason: str = "input_discontinuity") -> list[dict]:
        changes = []
        for event in self.active.values():
            event.update(state="resolved", ended_at=utc_now())
            event["quality_flags"] = list(set(event["quality_flags"] + [reason]))
            changes.append(event.copy())
        self.active.clear()
        self.candidates.clear()
        self.cooldowns.clear()
        self.line_states.clear()
        self.entries = self.exits = 0
        self.zone_counts = {}
        self.debug = []
        return changes

    def _make_event(
        self,
        kind: str,
        zone_id: str,
        zone_name: str,
        track_id: str | None,
        now: float,
        started: float,
        features: dict,
        explanation: str,
    ) -> dict:
        return {
            "id": str(uuid.uuid4()),
            "camera_id": self.camera_id,
            "type": kind,
            "state": "active",
            "review_status": "unreviewed",
            "severity": "review",
            "started_at": utc_now(),
            "ended_at": None,
            "window_started_at": (datetime.now(UTC) - timedelta(seconds=max(0, now - started)))
            .isoformat()
            .replace("+00:00", "Z"),
            "source_mode": self.mode,
            "model_version": self.model,
            "evidence_url": None,
            "quality_flags": ["uncalibrated_camera", "requires_human_review"],
            "rule_parameters": self.config.rules.model_dump(),
            "zone_id": zone_id,
            "zone_name": zone_name,
            "track_id": track_id,
            "explanation": explanation,
            "features": features,
        }

    def _transition(
        self,
        key: str,
        condition: bool,
        now: float,
        duration: float,
        kind: str,
        zone_id: str,
        name: str,
        track_id: str | None,
        features: dict,
        explanation: str,
    ) -> list[dict]:
        if condition:
            self.candidates.setdefault(key, now)
            elapsed = now - self.candidates[key]
            if key in self.active:
                self.active[key]["features"].update(features, observed_seconds=elapsed)
                return [self.active[key].copy()]
            if elapsed >= duration and now >= self.cooldowns.get(key, -1):
                event = self._make_event(
                    kind,
                    zone_id,
                    name,
                    track_id,
                    now,
                    self.candidates[key],
                    {**features, "observed_seconds": elapsed},
                    explanation,
                )
                self.active[key] = event
                return [event.copy()]
        else:
            self.candidates.pop(key, None)
            if key in self.active:
                event = self.active.pop(key)
                event.update(state="resolved", ended_at=utc_now())
                self.cooldowns[key] = now + self.config.rules.cooldown_seconds
                return [event.copy()]
        return []

    def step(self, tracks: list[Track], now: float, quality: bool = True) -> list[dict]:
        if not quality or self.mode == "SNAPSHOT":
            return self.reset("temporal_rules_suppressed")
        rules = self.config.rules
        ignored = [Polygon(z.points) for z in self.config.zones if z.kind == "ignore"]
        eligible = [
            t
            for t in tracks
            if t.detection.label == "person"
            and not any(p.covers(Point(t.detection.anchor)) for p in ignored)
        ]
        valid_ids = {t.id for t in eligible}
        # Drop departed track references; reappearance gets an unrelated session ID.
        self.line_states = {
            key: state for key, state in self.line_states.items() if key[1] in valid_ids
        }
        changes: list[dict] = []
        margin = rules.flow_crossing_margin
        for line in self.config.lines:
            for track in eligible:
                if now - track.born < rules.flow_track_maturity_seconds or not inside_segment(
                    line, track.detection.anchor
                ):
                    continue
                value = side(line, track.detection.anchor)
                current = 1 if value > margin else -1 if value < -margin else 0
                if not current:
                    continue
                line_key = (line.id, track.id)
                previous = self.line_states.get(line_key)
                if previous is None:
                    self.line_states[line_key] = LineTrack(current)
                elif previous.side != current:
                    if now - previous.last_counted >= rules.flow_crossing_cooldown:
                        if previous.side == -1:
                            self.entries += 1
                        else:
                            self.exits += 1
                        previous.last_counted = now
                    previous.side = current
        self.zone_counts = {}
        self.debug = []
        touched: set[str] = set()
        for zone in self.config.zones:
            if zone.kind != "monitoring_lane":
                continue
            polygon = Polygon(zone.points)
            members = [t for t in eligible if polygon.covers(Point(t.detection.anchor))]
            self.zone_counts[zone.id] = len(members)
            # Whole-frame presets are observational counters, not waiting zones.
            # A near-whole-frame polygon must not imply a person is queuing.
            # The starter waiting-area box is only a placement template. Never
            # generate service alerts from it before the operator explicitly
            # adjusts and renames it as a real area. Existing records remain
            # archived, but future placeholder alerts are suppressed.
            is_unconfirmed_template = (
                zone.id == "quick-waiting-area" and "adjust location" in zone.name.lower()
            )
            if zone.id == "quick-whole-frame" or polygon.area >= 0.85 or is_unconfirmed_template:
                self.debug.append(
                    {
                        "zone_id": zone.id,
                        "name": zone.name,
                        "count": len(members),
                        "occupancy": min(1.0, len(members) / max(1, rules.flow_capacity)),
                        "motion": 0.0,
                        "baseline": {"occupancy": 0.0, "motion": 0.0},
                        "warming_up": False,
                        "general_stop_suppression": False,
                        "candidate_count": 0,
                        "queue_state": (
                            "template_unconfirmed" if is_unconfirmed_template else "count_only"
                        ),
                    }
                )
                continue
            for track in members:
                key = f"dwell:{zone.id}:{track.id}"
                touched.add(key)
                changes += self._transition(
                    key,
                    True,
                    now,
                    rules.flow_dwell_seconds,
                    "extended_dwell",
                    zone.id,
                    zone.name,
                    track.id,
                    {
                        "motion_normalized_per_second": track.motion,
                        "required_seconds": rules.flow_dwell_seconds,
                    },
                    f"Person remained inside {zone.name} for the configured duration. "
                    "This is not proof of a queue or an individual's intentions.",
                )
            slow = [
                t
                for t in members
                if t.motion <= rules.flow_motion_threshold
                and now - t.born >= rules.flow_track_maturity_seconds
            ]
            key = f"queue:{zone.id}"
            touched.add(key)
            condition = len(members) >= rules.flow_queue_people and (
                len(slow) / len(members) >= rules.flow_slow_fraction
            )
            changes += self._transition(
                key,
                condition,
                now,
                rules.flow_queue_seconds,
                "possible_queue_buildup",
                zone.id,
                zone.name,
                None,
                {
                    "people_in_zone": len(members),
                    "low_motion_people": len(slow),
                    "required_seconds": rules.flow_queue_seconds,
                },
                f"Several tracked people occupied {zone.name} with sustained low motion. "
                "Standing together does not necessarily mean queuing.",
            )
            self.debug.append(
                {
                    "zone_id": zone.id,
                    "name": zone.name,
                    "count": len(members),
                    "occupancy": min(1.0, len(members) / max(1, rules.flow_capacity)),
                    "motion": statistics.median(t.motion for t in members) if members else 0.0,
                    "baseline": {"occupancy": 0.0, "motion": 0.0},
                    "warming_up": False,
                    "general_stop_suppression": False,
                    "candidate_count": sum(
                        k.startswith(f"dwell:{zone.id}:") for k in self.candidates
                    ),
                    "queue_state": "active"
                    if key in self.active
                    else "candidate"
                    if key in self.candidates
                    else "clear",
                }
            )
        for key in set(self.candidates) | set(self.active):
            if key not in touched:
                changes += self._transition(key, False, now, 0, "", "", "", None, {}, "")
        self.cooldowns = {k: v for k, v in self.cooldowns.items() if v > now}
        return changes
