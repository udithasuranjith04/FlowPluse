import os
import time

import cv2

from app.evidence import EvidenceStore


def test_retention_off_by_default(tmp_path):
    evidence = EvidenceStore(tmp_path / "evidence", False, 24)
    assert evidence.save("example", []) is None
    assert not (tmp_path / "evidence").exists()


def test_redaction_failure_never_writes(tmp_path, monkeypatch):
    evidence = EvidenceStore(tmp_path / "evidence", True, 24)
    monkeypatch.setattr(cv2, "imencode", lambda *a: (False, None))
    assert evidence.save("example", []) is None
    assert not (tmp_path / "evidence").exists()


def test_retained_schematic_has_no_source_pixels_and_expires(tmp_path):
    evidence = EvidenceStore(tmp_path, True, 1)
    assert evidence.save("example", [])
    path = tmp_path / "example.jpg"
    assert path.exists()
    os.utime(path, (time.time() - 7200, time.time() - 7200))
    evidence.purge()
    assert not path.exists()


def test_expired_evidence_is_not_served_when_cleanup_fails(tmp_path, monkeypatch):
    from pathlib import Path

    evidence = EvidenceStore(tmp_path, True, 1)
    evidence.save("example", [])
    path = tmp_path / "example.jpg"
    os.utime(path, (time.time() - 7200, time.time() - 7200))

    def refuse_delete(self, **kwargs):
        raise PermissionError("test filesystem permission failure")

    monkeypatch.setattr(Path, "unlink", refuse_delete)
    assert evidence.get("example") is None
    assert evidence.last_error is not None
