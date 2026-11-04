"""The release cleanup utility must not touch live application source."""

from pathlib import Path

from scripts.release_prep import find_artifacts, quarantine, unsafe_tracked


def test_find_only_known_patch_leftovers(tmp_path: Path) -> None:
    (tmp_path / "backend" / "app").mkdir(parents=True)
    (tmp_path / "backend" / "app" / "main.py").write_text("real source")
    (tmp_path / "backend" / "app" / "main.py.orig").write_text("patch backup")
    (tmp_path / "backend" / "app" / "main.py.rej").write_text("rejected hunk")
    (tmp_path / "runtime").mkdir()
    (tmp_path / "runtime" / "model.pt").write_text("must not move")
    (tmp_path / "flowpulse-wired-repair-v2-backup-123").mkdir()
    (tmp_path / "PROJECT_REVIEW_MANIFEST.txt").write_text("metadata")

    names = {x.relative_to(tmp_path).as_posix() for x in find_artifacts(tmp_path)}
    assert names == {
        "backend/app/main.py.orig",
        "backend/app/main.py.rej",
        "flowpulse-wired-repair-v2-backup-123",
        "PROJECT_REVIEW_MANIFEST.txt",
    }
    destination = tmp_path.parent / "quarantine"
    quarantine(tmp_path, find_artifacts(tmp_path), set(), destination)
    assert (tmp_path / "backend" / "app" / "main.py").read_text() == "real source"
    assert (tmp_path / "runtime" / "model.pt").exists()
    assert (destination / "backend" / "app" / "main.py.orig").exists()
    assert not (tmp_path / "backend" / "app" / "main.py.rej").exists()


def test_quarantine_does_not_move_tracked_reject(tmp_path: Path) -> None:
    backup = tmp_path / "file.py.rej"
    backup.write_text("keep")
    moved = quarantine(tmp_path, [backup], {"file.py.rej"}, tmp_path.parent / "unused")
    assert moved == []
    assert backup.exists()


def test_unsafe_tracked_files() -> None:
    assert unsafe_tracked("backend/app/main.py") is False
    assert unsafe_tracked(".env.example") is False
    assert unsafe_tracked(".env") is True
    assert unsafe_tracked("scripts/foo.py.orig") is True
    assert unsafe_tracked("runtime/models/yolo11n.pt") is True
    assert unsafe_tracked("frontend/node_modules/foo.js") is True
    assert unsafe_tracked("frontend/tsconfig.tsbuildinfo") is True


def test_unsafe_tracked_backup_directory() -> None:
    assert unsafe_tracked("flowpulse-wired-repair-v2-backup-123/backend/app/main.py")
