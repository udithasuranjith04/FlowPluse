"""Report GitHub release hazards; optionally quarantine obsolete patch backups.

The default mode is read-only. ``--quarantine`` moves only recognized
repair artifacts to ~/Downloads, not application source, camera footage or
runtime data. This utility never edits Git history or creates a release.
"""

import argparse
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEARCH_SKIP = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "runtime",
    ".idea",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    "__pycache__",
    "dist",
    "build",
    "test-results",
    "playwright-report",
}


def is_repair_artifact(path: Path, root: Path) -> bool:
    """Identify obsolete patch backups, never active project files."""
    relative = path.relative_to(root)
    name = path.name
    if (
        len(relative.parts) == 1
        and name.startswith("flowpulse-")
        and "-backup-" in name
    ):
        return path.is_dir()
    if len(relative.parts) == 1 and name == "PROJECT_REVIEW_MANIFEST.txt":
        return path.is_file()
    return path.is_file() and (
        name.endswith((".orig", ".rej", ".bak")) or ".backup-" in name
    )


def find_artifacts(root: Path) -> list[Path]:
    result: list[Path] = []
    for folder, directories, files in os.walk(root, followlinks=False):
        directory = Path(folder)
        remaining: list[str] = []
        for name in sorted(directories):
            candidate = directory / name
            if name in SEARCH_SKIP or candidate.is_symlink():
                continue
            if is_repair_artifact(candidate, root):
                result.append(candidate)
            else:
                remaining.append(name)
        directories[:] = remaining
        for name in sorted(files):
            candidate = directory / name
            if not candidate.is_symlink() and is_repair_artifact(candidate, root):
                result.append(candidate)
    return sorted(result)


def tracked_files(root: Path) -> set[str] | None:
    try:
        probe = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
            capture_output=True,
            check=False,
            text=True,
        )
        if (
            probe.returncode != 0
            or Path(probe.stdout.strip()).resolve() != root.resolve()
        ):
            return None
        tracked = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"],
            capture_output=True,
            check=False,
        )
        if tracked.returncode != 0:
            return None
        return {
            x.decode("utf-8", errors="replace")
            for x in tracked.stdout.split(b"\0")
            if x
        }
    except OSError:
        return None


def unsafe_tracked(path: str) -> bool:
    file = Path(path)
    basename = file.name.lower()
    parts = set(file.parts)
    if basename in {".env.example", ".env.sample"}:
        return False
    if basename == ".env" or basename.startswith(".env."):
        return True
    if parts.intersection(
        {"runtime", "node_modules", ".venv", ".idea", "test-results"}
    ):
        return True
    if basename == "project_review_manifest.txt":
        return True
    if basename.endswith(
        (
            ".orig",
            ".rej",
            ".bak",
            ".pt",
            ".pth",
            ".onnx",
            ".db",
            ".sqlite",
            ".sqlite3",
            ".mp4",
            ".mov",
            ".avi",
            ".webm",
            ".pem",
            ".p12",
            ".pfx",
            ".key",
            ".tsbuildinfo",
        )
    ):
        return True
    return bool(
        ".backup-" in basename
        or any(
            part.startswith("flowpulse-") and "-backup-" in part for part in file.parts
        )
    )


def quarantine(
    root: Path, items: list[Path], tracked: set[str] | None, dest: Path
) -> list[Path]:
    """Move untracked leftovers preserving their relative paths."""
    moved: list[Path] = []
    for item in items:
        relative = item.relative_to(root)
        # Never change the working tree's tracked history by surprise.
        if tracked is not None and any(
            value == relative.as_posix() or value.startswith(relative.as_posix() + "/")
            for value in tracked
        ):
            print(f"SKIPPED tracked artifact: {relative}")
            continue
        target = dest / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            raise FileExistsError(f"Quarantine destination already exists: {target}")
        shutil.move(str(item), str(target))
        moved.append(relative)
    return moved


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--quarantine",
        action="store_true",
        help="Move known patch leftovers into ~/Downloads",
    )
    args = parser.parse_args()
    items = find_artifacts(ROOT)
    tracked = tracked_files(ROOT)
    print(f"FlowPulse release preflight: {ROOT}")
    print(f"Old patch/backup artifacts found: {len(items)}")
    for item in items:
        print(f"  {item.relative_to(ROOT)}")

    if tracked is None:
        print("Git status: not an initialized root repository (or Git unavailable).")
        print("Check 'git status' and 'git remote -v' on your Mac before publishing.")
        risky: list[str] = []
    else:
        risky = sorted(path for path in tracked if unsafe_tracked(path))
        print(f"Git tracked files checked: {len(tracked)}")
        if risky:
            print("WARNING: release-unsafe files are already TRACKED:")
            for path in risky:
                print(f"  {path}")
            print(".gitignore cannot untrack a file already committed.")

    if args.quarantine and items:
        destination = (
            Path.home()
            / "Downloads"
            / (
                "FlowPulse-release-quarantine-"
                + datetime.now().strftime("%Y%m%d-%H%M%S")
            )
        )
        moved = quarantine(ROOT, items, tracked, destination)
        if moved:
            print(f"Moved {len(moved)} obsolete files/directories to: {destination}")
        else:
            print("No files moved; tracked files require a deliberate Git review.")
    elif not args.quarantine and items:
        print("Read-only mode: run with --quarantine to move, not delete, these files.")

    if risky:
        print("FAIL: resolve tracked release-unsafe files before a public push.")
        return 1
    print(
        "Preflight complete. Manual source/secret review and Mac checks still required."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
