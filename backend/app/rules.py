import statistics
import uuid
from collections import deque
from datetime import UTC, datetime, timedelta

from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union

from app.schemas import ZoneConfig
from app.tracking import Track


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def zone_features(tracks: list[Track], polygon: Polygon) -> dict:
    intersections = [box(*t.detection.box).intersection(polygon) for t in tracks]
    occupancy = unary_union(intersections).area / polygon.area if intersections else 0.0
    return {
        "count": len(tracks),
        "occupancy": min(1.0, occupancy),
        "motion": statistics.median(t.motion for t in tracks) if tracks else 0.0,
    }


class RuleEngine:
    def __init__(self, camera_id: str, config: ZoneConfig, mode: str, model: str):
        self.camera_id, self.config, self.mode, self.model = camera_id, config, mode, model
        self.candidates: dict[str, float] = {}
        self.active: dict[str, dict] = {}
        self.cooldowns: dict[str, float] = {}
        self.baselines: dict[str, deque] = {}
        self.baseline_values: dict[str, dict] = {}
        self.debug: list[dict] = []

    def reset(self, reason: str = "input_discontinuity") -> list[dict]:
        ended = []
        for event in self.active.values():
            event.update(state="resolved", ended_at=utc_now())
            event["quality_flags"] = list(set(event["quality_flags"] + [reason]))
            ended.append(event.copy())
        self.candidates.clear()
        self.active.clear()
        self.baselines.clear()
        self.baseline_values.clear()
        self.debug = []
        return ended

    def _transition(
        self,
        key: str,
        condition: bool,
        duration: float,
        now: float,
        payload: dict,
        retain: bool = False,
    ) -> list[dict]:
        if condition:
            self.candidates.setdefault(key, now)
            observed = now - self.candidates[key]
            if key in self.active:
                event = self.active[key]
                event["features"].update(payload["features"], observed_seconds=observed)
                return [event.copy()]
            if observed >= duration and now >= self.cooldowns.get(key, -1):
                event = {
                    "id": str(uuid.uuid4()),
                    "camera_id": self.camera_id,
                    "state": "active",
                    "review_status": "unreviewed",
                    "severity": "review",
                    "started_at": utc_now(),
                    "ended_at": None,
                    "window_started_at": (datetime.now(UTC) - timedelta(seconds=observed))
                    .isoformat()
                    .replace("+00:00", "Z"),
                    "source_mode": self.mode,
                    "model_version": self.model,
                    "evidence_url": None,
                    "quality_flags": [
                        "uncalibrated_camera",
                        "signal_phase_unknown",
                        "requires_human_review",
                    ],
                    "rule_parameters": self.config.rules.model_dump(),
                    **payload,
                }
                if self.mode == "REPLAY":
                    event["quality_flags"].append("replay_input")
                event["features"]["observed_seconds"] = observed
                self.active[key] = event
                return [event.copy()]
        elif not retain:
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
        cfg = self.config.rules
        ignored = [Polygon(z.points) for z in self.config.zones if z.kind == "ignore"]
        eligible = [
            t for t in tracks if not any(p.covers(Point(t.detection.anchor)) for p in ignored)
        ]
        changes = []
        touched = set()
        self.debug = []
        for zone in self.config.zones:
            if zone.kind != "monitoring_lane":
                continue
            polygon = Polygon(zone.points)
            members = [t for t in eligible if polygon.covers(Point(t.detection.anchor))]
            metrics = zone_features(members, polygon)
            mature = [t for t in members if now - t.born >= cfg.min_track_age]
            stopped = [t for t in mature if t.motion <= cfg.motion_threshold]
            general_stop = len(mature) >= 3 and len(stopped) / len(mature) >= 0.65
            for track in members:
                key = f"stop:{zone.id}:{track.id}"
                touched.add(key)
                changes += self._transition(
                    key,
                    track in stopped and not general_stop,
                    cfg.stationary_seconds,
                    now,
                    {
                        "type": "potential_stopped_vehicle",
                        "zone_id": zone.id,
                        "zone_name": zone.name,
                        "track_id": track.id,
                        "explanation": "Anchor motion stayed below the configured threshold "
                        f"in {zone.name}. Signals, queues or occlusion can cause false alarms.",
                        "features": {
                            "motion_normalized_per_second": track.motion,
                            "threshold": cfg.motion_threshold,
                            "required_seconds": cfg.stationary_seconds,
                            "track_age_seconds": now - track.born,
                            "detection_confidence": track.detection.confidence,
                        },
                    },
                )
            history = self.baselines.setdefault(zone.id, deque(maxlen=10000))
            key = f"queue:{zone.id}"
            touched.add(key)
            warm = bool(history) and now - history[0][0] >= cfg.baseline_window
            if key not in self.candidates and key not in self.active:
                baseline = {
                    "occupancy": statistics.mean(v[1] for v in history) if history else 0,
                    "motion": statistics.mean(v[2] for v in history) if history else 0,
                }
                self.baseline_values[zone.id] = baseline
            baseline = self.baseline_values.get(zone.id, {"occupancy": 0, "motion": 0})
            congested = (
                warm
                and metrics["count"] >= 3
                and metrics["occupancy"] >= cfg.occupancy_threshold
                and metrics["occupancy"] - baseline["occupancy"] >= cfg.occupancy_increase
                and baseline["motion"] > cfg.motion_threshold
                and metrics["motion"] <= baseline["motion"] * 0.5
            )
            retain = (
                key in self.active
                and metrics["count"] >= 3
                and metrics["occupancy"] >= cfg.occupancy_threshold * 0.7
                and metrics["motion"] <= baseline["motion"] * 0.75
            )
            changes += self._transition(
                key,
                congested,
                cfg.congestion_seconds,
                now,
                {
                    "type": "congestion_buildup",
                    "zone_id": zone.id,
                    "zone_name": zone.name,
                    "track_id": None,
                    "explanation": f"Possible queue buildup in {zone.name}: occupancy increased "
                    "and image-plane movement fell relative to this lane's baseline. "
                    "Signal phases and camera perspective are not calibrated.",
                    "features": {
                        **metrics,
                        "baseline": baseline.copy(),
                        "baseline_window_seconds": cfg.baseline_window,
                        "required_seconds": cfg.congestion_seconds,
                    },
                },
                retain=retain,
            )
            # Freeze reference during a buildup, rather than adapting away a sustained queue.
            if key not in self.candidates and key not in self.active:
                history.append((now, metrics["occupancy"], metrics["motion"]))
                while len(history) > 1 and now - history[1][0] > cfg.baseline_window:
                    history.popleft()
            self.debug.append(
                {
                    "zone_id": zone.id,
                    "name": zone.name,
                    **metrics,
                    "baseline": baseline,
                    "warming_up": not warm,
                    "general_stop_suppression": general_stop,
                    "candidate_count": sum(
                        k.startswith(f"stop:{zone.id}:") for k in self.candidates
                    ),
                    "queue_state": "active"
                    if key in self.active
                    else "candidate"
                    if key in self.candidates
                    else "warming_up"
                    if not warm
                    else "clear",
                }
            )
        for key in set(self.candidates) | set(self.active):
            if key not in touched:
                changes += self._transition(key, False, 0, now, {})
        self.cooldowns = {k: t for k, t in self.cooldowns.items() if t > now}
        return changes
