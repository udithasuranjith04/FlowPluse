"""Explicit opt-in model download. Requires network and the optional vision extra."""

import hashlib
import os
from pathlib import Path


def main() -> None:
    os.environ["YOLO_CONFIG_DIR"] = str(Path("runtime/ultralytics").resolve())
    os.environ["YOLO_AUTOINSTALL"] = "false"
    from ultralytics import YOLO, settings

    settings.update({"sync": False})

    directory = Path("runtime/models").resolve()
    directory.mkdir(parents=True, exist_ok=True)
    os.chdir(directory)
    YOLO("yolo11n.pt")
    file = directory / "yolo11n.pt"
    if not file.is_file():
        raise SystemExit("Model download did not produce the expected file.")
    print("Downloaded YOLO11n from the Ultralytics downloader. AGPL-3.0 terms apply.")
    print(f"SHA-256: {hashlib.sha256(file.read_bytes()).hexdigest()}")
    print("Record this digest for your environment. Never load untrusted .pt files.")


if __name__ == "__main__":
    main()
