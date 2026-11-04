import pytest
from pydantic import ValidationError
from shapely.geometry import Point, Polygon

from app.schemas import Zone, ZoneConfig


@pytest.mark.parametrize(
    "points",
    [
        [(0, 0), (1, 1)],
        [(0, 0), (0, 0.5), (0, 1)],
        [(0, 0), (1, 1), (1, 0), (0, 1)],
        [(0, 0), (1.1, 0), (0.5, 1)],
        [(0, 0), (float("nan"), 0), (0.5, 1)],
    ],
)
def test_reject_invalid_polygon(points):
    with pytest.raises(ValidationError):
        Zone(id="lane", name="Lane", points=points)


def test_boundaries_and_duplicate_ids():
    zone = Zone(id="lane", name="Lane", points=[(0, 0), (1, 0), (0, 1)])
    assert Polygon(zone.points).covers(Point(0, 0.5))
    with pytest.raises(ValidationError):
        ZoneConfig(zones=[zone, zone])


def test_staff_only_region_is_validated_and_not_an_identity_setting():
    assert ZoneConfig().staff_only_region == "none"
    assert ZoneConfig(staff_only_region="top").staff_only_region == "top"
    with pytest.raises(ValidationError):
        ZoneConfig(staff_only_region="identify_staff")
