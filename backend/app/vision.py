import os
import time
from pathlib import Path

import cv2
import numpy as np

from app.tracking import Detection

VEHICLE_COLORS = {
    "car": (210, 170, 50),
    "truck": (70, 150, 230),
    "bus": (180, 100, 210),
    "motorcycle": (110, 210, 100),
}


class SyntheticDetector:
    name = "Synthetic color detector v1 (fixture only)"

    def detect(self, frame: np.ndarray, confidence: float = 0.35) -> list[Detection]:
        height, width = frame.shape[:2]
        result = []
        for label, color in VEHICLE_COLORS.items():
            color_array = np.array(color, dtype=np.int16)
            mask = cv2.inRange(
                frame,
                np.maximum(color_array - 3, 0).astype(np.uint8),
                np.minimum(color_array + 3, 255).astype(np.uint8),
            )
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for contour in contours:
                x, y, w, h = cv2.boundingRect(contour)
                if w * h > 80:
                    result.append(
                        Detection(
                            (x / width, y / height, (x + w) / width, (y + h) / height), label, 1.0
                        )
                    )
        return result


class YoloDetector:
    def __init__(self, model_path: str, device: str, target: str = "vehicle"):
        if target not in {"vehicle", "person"}:
            raise ValueError("Detector target must be vehicle or person")
        self.target = target
        if not Path(model_path).is_file():
            raise RuntimeError(
                "Model weights missing. Run make model before activating this source."
            )
        os.environ["YOLO_OFFLINE"] = "true"
        os.environ["YOLO_AUTOINSTALL"] = "false"
        os.environ["YOLO_CONFIG_DIR"] = str(Path("runtime/ultralytics").resolve())
        try:
            from ultralytics import YOLO, settings
        except ImportError as exc:
            raise RuntimeError("Live detector unavailable. Install backend[vision] first.") from exc
        settings.update({"sync": False})
        self.model = YOLO(model_path)
        self.device = device
        self.device_note: str | None = None
        # Person detection benefits from larger input pixels in distant café
        # scenes. Back off automatically if this Mac cannot keep up.
        self.person_image_size = 960
        self._slow_detail_samples = 0
        if device == "mps":
            import torch

            if not torch.backends.mps.is_available():
                self.device = "cpu"
                self.device_note = "MPS unavailable; using CPU."

        from importlib.metadata import version

        self.name = f"Ultralytics {version('ultralytics')} / {Path(model_path).name}"

    def detect(self, frame: np.ndarray, confidence: float = 0.35) -> list[Detection]:
        started = time.perf_counter()
        try:
            prediction = self._predict(frame, confidence)
        except (RuntimeError, NotImplementedError):
            if self.device != "mps":
                raise
            self.device = "cpu"
            self.device_note = "MPS inference failed; using CPU."
            self.model.to("cpu")
            prediction = self._predict(frame, confidence)
        if getattr(self, "target", "vehicle") == "person":
            elapsed = time.perf_counter() - started
            self._slow_detail_samples = (
                getattr(self, "_slow_detail_samples", 0) + 1 if elapsed > 0.42 else 0
            )
            if self._slow_detail_samples >= 5 and self.person_image_size > 640:
                # Keep the smooth camera preview independent from inference.
                # Avoid overloading CPU/MPS on slower Macs or complex scenes.
                self.person_image_size = {960: 832, 832: 736, 736: 640}.get(
                    self.person_image_size, 640
                )
                self._slow_detail_samples = 0
        result = []
        if prediction.boxes is not None:
            for box, score, category in zip(
                prediction.boxes.xyxyn.cpu().tolist(),
                prediction.boxes.conf.cpu().tolist(),
                prediction.boxes.cls.cpu().tolist(),
                strict=True,
            ):
                result.append(
                    Detection(
                        (box[0], box[1], box[2], box[3]), self.model.names[int(category)], score
                    )
                )
        return result

    def _predict(self, frame: np.ndarray, confidence: float):
        from ultralytics.engine.results import Results

        predictions = self.model.predict(
            frame,
            conf=confidence,
            classes=[0] if self.target == "person" else [2, 3, 5, 7],
            imgsz=getattr(self, "person_image_size", 960) if self.target == "person" else 640,
            device=self.device,
            verbose=False,
            save=False,
            save_txt=False,
            save_crop=False,
            show=False,
        )
        if not isinstance(predictions, list) or len(predictions) != 1:
            raise RuntimeError("Detector returned an unexpected result batch")
        result = predictions[0]
        if not isinstance(result, Results):
            raise RuntimeError("Detector did not return detection results")
        return result
