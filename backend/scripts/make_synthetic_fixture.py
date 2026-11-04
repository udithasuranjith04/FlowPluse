"""Generate original synthetic development footage; never downloads footage."""

from pathlib import Path

import cv2

from app.synthetic import render_frame


def main() -> None:
    path = Path("runtime/synthetic-replay.avi")
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 10, (960, 540))
    if not writer.isOpened():
        raise SystemExit("MJPEG encoder unavailable in this OpenCV build")
    try:
        for i in range(800):
            writer.write(render_frame(i / 10))
    finally:
        writer.release()
    print(f"Generated {path}: 80 seconds, 10 FPS. Synthetic fixture only.")


if __name__ == "__main__":
    main()
