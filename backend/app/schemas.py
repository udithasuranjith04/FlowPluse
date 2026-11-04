import math
from typing import Literal

from pydantic import BaseModel, Field, model_validator
from shapely.geometry import Polygon

Point = tuple[float, float]


class Zone(BaseModel):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,50}$")
    name: str = Field(min_length=1, max_length=80)
    kind: Literal["monitoring_lane", "ignore"] = "monitoring_lane"
    points: list[Point] = Field(min_length=3, max_length=40)

    @model_validator(mode="after")
    def valid_polygon(self):
        if not all(math.isfinite(n) and 0 <= n <= 1 for p in self.points for n in p):
            raise ValueError("Coordinates must be finite and normalized to [0, 1]")
        poly = Polygon(self.points)
        if not poly.is_valid or poly.area < 0.0001:
            raise ValueError("Polygon must have nonzero area and no self intersections")
        return self


class FlowLine(BaseModel):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,50}$")
    name: str = Field(min_length=1, max_length=80)
    points: tuple[Point, Point]

    @model_validator(mode="after")
    def valid_line(self):
        if not all(math.isfinite(n) and 0 <= n <= 1 for p in self.points for n in p):
            raise ValueError("Counting line coordinates must be normalized")
        if math.dist(*self.points) < 0.02:
            raise ValueError("Counting line must be at least 2% of the image diagonal")
        return self


class RuleConfig(BaseModel):
    flow_track_maturity_seconds: float = Field(default=1, ge=0.5, le=30)
    flow_dwell_seconds: float = Field(default=15, ge=2, le=600)
    flow_queue_people: int = Field(default=3, ge=2, le=100)
    flow_queue_seconds: float = Field(default=15, ge=2, le=600)
    flow_motion_threshold: float = Field(default=0.008, ge=0.0001, le=0.1)
    flow_slow_fraction: float = Field(default=0.7, ge=0.5, le=1)
    flow_capacity: int = Field(default=10, ge=1, le=500)
    flow_crossing_margin: float = Field(default=0.012, ge=0.002, le=0.1)
    flow_crossing_cooldown: float = Field(default=2, ge=0.1, le=30)
    stationary_seconds: float = Field(default=12, ge=2, le=300)
    min_track_age: float = Field(default=8, ge=1, le=120)
    motion_threshold: float = Field(default=0.005, ge=0.0001, le=0.1)
    occupancy_threshold: float = Field(default=0.16, ge=0.01, le=0.9)
    occupancy_increase: float = Field(default=0.08, ge=0.01, le=0.8)
    baseline_window: float = Field(default=20, ge=5, le=600)
    congestion_seconds: float = Field(default=20, ge=2, le=300)
    cooldown_seconds: float = Field(default=60, ge=1, le=3600)
    min_confidence: float = Field(default=0.35, ge=0.1, le=0.95)
    target_fps: float = Field(default=2, ge=0.5, le=15)


class ZoneConfig(BaseModel):
    # Geometry hint only: no person role or identity is inferred.
    # A single operator-confirmed staff-only side can be excluded from a
    # separate guest-facing *area* count. Full-frame counts remain unchanged.
    staff_only_region: Literal["none", "left", "right", "top", "bottom"] = "none"
    lines: list[FlowLine] = Field(default_factory=list, max_length=12)
    zones: list[Zone] = Field(default_factory=list, max_length=20)
    rules: RuleConfig = Field(default_factory=RuleConfig)

    @model_validator(mode="after")
    def unique_ids(self):
        if len({z.id for z in self.zones}) != len(self.zones):
            raise ValueError("Zone IDs must be unique")
        if len({line.id for line in self.lines}) != len(self.lines):
            raise ValueError("Counting line IDs must be unique")
        return self


class ReviewUpdate(BaseModel):
    review_status: Literal["unreviewed", "acknowledged", "false_alarm"]


def demo_zones() -> ZoneConfig:
    return ZoneConfig(
        zones=[
            Zone(
                id="eastbound",
                name="Eastbound monitoring lane",
                points=[(0.05, 0.27), (0.95, 0.27), (0.95, 0.83), (0.05, 0.83)],
            )
        ]
    )
