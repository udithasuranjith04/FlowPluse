from pathlib import Path

import pytest


@pytest.fixture
def settings(tmp_path: Path):
    from app.config import Settings

    return Settings(
        _env_file=None,
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        evidence_dir=tmp_path / "evidence",
        autostart=False,
        detection_target="vehicle",  # Legacy traffic fixtures remain vehicle-specific.
    )


@pytest.fixture
def client(settings):
    from fastapi.testclient import TestClient

    from app.main import create_app

    with TestClient(create_app(settings)) as test_client:
        yield test_client


@pytest.fixture
def fast_config():
    from app.schemas import RuleConfig, Zone, ZoneConfig

    return ZoneConfig(
        zones=[Zone(id="lane", name="Test lane", points=[(0, 0), (1, 0), (1, 1), (0, 1)])],
        rules=RuleConfig(
            stationary_seconds=2,
            min_track_age=1,
            baseline_window=5,
            congestion_seconds=2,
            cooldown_seconds=5,
            occupancy_threshold=0.1,
            occupancy_increase=0.05,
        ),
    )
