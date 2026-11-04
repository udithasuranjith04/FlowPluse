import cv2
import numpy as np

from app.vision import VEHICLE_COLORS


def render_frame(seconds: float, width: int = 960, height: int = 540) -> np.ndarray:
    """An original 80-second scenario: moving traffic, one stop, then a queue and clearance."""
    t = seconds % 80
    frame = np.full((height, width, 3), (25, 35, 39), np.uint8)
    cv2.rectangle(frame, (0, int(height * 0.25)), (width, int(height * 0.86)), (53, 62, 68), -1)
    for y in (0.27, 0.84):
        cv2.line(frame, (0, int(height * y)), (width, int(height * y)), (143, 151, 149), 2)
    for y in (0.45, 0.64):
        for x in range(-20, width, 80):
            cv2.line(frame, (x, int(height * y)), (x + 35, int(height * y)), (107, 119, 123), 2)
    for x in range(40, width, 130):
        cv2.circle(frame, (x, 75), 24, (38, 67, 55), -1)
        cv2.circle(frame, (x + 30, height - 40), 18, (38, 67, 55), -1)

    def vehicle(x: float, y: float, label: str, size: float = 0.075) -> None:
        x1, y1 = int(x * width), int(y * height)
        w, h = int(size * width), int(0.095 * height)
        cv2.rectangle(frame, (x1 + 3, y1 + 5), (x1 + w + 3, y1 + h + 5), (26, 31, 34), -1)
        cv2.rectangle(frame, (x1, y1), (x1 + w, y1 + h), VEHICLE_COLORS[label], -1)
        cv2.rectangle(frame, (x1 + w // 2, y1 + 7), (x1 + w - 9, y1 + h - 7), (58, 70, 77), -1)

    # A persistent stopped track, while others keep moving, then a clean departure.
    x_stop = 0.10 + min(t, 5) * 0.035 if t < 24 else 0.275 + (t - 24) * 0.045
    if x_stop < 0.95:
        vehicle(x_stop, 0.31, "car")
    if t < 32 or t >= 64:
        for offset, y, label in ((0, 0.50, "truck"), (0.38, 0.69, "car"), (0.7, 0.50, "bus")):
            vehicle((t * 0.035 + offset) % 1.15 - 0.1, y, label, 0.11 if label != "car" else 0.075)
    else:
        for i in range(5):
            for j, label in enumerate(("car", "truck", "bus")):
                vehicle(0.10 + i * 0.16 + max(0, 38 - t) * 0.012, 0.31 + j * 0.19, label, 0.115)
    cv2.putText(
        frame,
        "SYNTHETIC REPLAY  /  NO REAL CAMERA",
        (28, 28),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.52,
        (171, 189, 194),
        1,
        cv2.LINE_AA,
    )
    cv2.putText(
        frame,
        f"SCENARIO {t:05.1f}s / 80s",
        (28, height - 17),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.48,
        (171, 189, 194),
        1,
        cv2.LINE_AA,
    )
    return frame
