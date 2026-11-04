import socket

import pytest

from app.sources import SourceError, validate_source


def test_permission_gate(settings):
    settings.camera_mode = "live"
    settings.camera_url = "https://camera.example/stream?token=private"
    with pytest.raises(SourceError, match="permission"):
        validate_source(settings)


def test_host_allowlist_and_private_network_default(settings, monkeypatch):
    settings.camera_mode = "live"
    settings.camera_url = "http://camera.example/stream"
    settings.camera_analysis_authorized = settings.camera_redisplay_authorized = True
    settings.camera_permission_notes = "Operator owns camera"
    settings.camera_permission_checked = "2026-10-31"
    with pytest.raises(SourceError, match="allowlisted"):
        validate_source(settings)
    settings.camera_allowed_hosts = "camera.example"
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a: [(2, 1, 6, "", ("127.0.0.1", 80))])
    with pytest.raises(SourceError, match="Private-network"):
        validate_source(settings)
    settings.camera_allow_private = True
    assert validate_source(settings) == settings.camera_url


def test_arbitrary_scheme_rejected(settings):
    settings.camera_analysis_authorized = settings.camera_redisplay_authorized = True
    settings.camera_permission_notes = "test"
    settings.camera_permission_checked = "2026-10-31"
    settings.camera_mode = "live"
    settings.camera_url = "file:///etc/passwd"
    with pytest.raises(SourceError, match="HTTP"):
        validate_source(settings)
