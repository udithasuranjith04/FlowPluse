"""Owned camera capture isolated from FastAPI and inference.

AVFoundation open/read can block. A disposable process bounds parent waits and
shutdown; its one-frame queue prevents camera buffers backing up behind YOLO.
"""

import json
import multiprocessing as mp
import platform
import queue
import subprocess
import sys
import time

import cv2

from app.sources import SourceError


def list_devices() -> dict:
    if platform.system() != "Darwin":
        return {
            "devices": [],
            "discovery_available": False,
            "message": "Native camera discovery is available on macOS only.",
        }
    try:
        result = subprocess.run(
            [sys.executable, "-m", "app.avfoundation"],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
        if result.returncode != 0:
            raise ValueError("Native discovery failed")
        devices = json.loads(result.stdout)
        return {
            "devices": devices,
            "discovery_available": True,
            "message": (
                "AVFoundation camera names; opening and actual frames are verified in Preview. "
                "Refresh after connecting your iPhone."
                if devices
                else "macOS exposes no cameras to this process. Connect/unlock the iPhone, enable "
                "Continuity Camera, and allow the launching app in macOS Camera privacy settings; "
                "then refresh. No device index is assumed."
            ),
        }
    except (OSError, subprocess.TimeoutExpired, ValueError, AttributeError):
        return {
            "devices": [],
            "discovery_available": False,
            "message": "Native AVFoundation discovery failed or timed out. Retry from the "
            "camera-authorized Terminal/app. No camera was opened.",
        }


def resolve_device(device_id: str) -> dict:
    result = list_devices()
    if not result["discovery_available"]:
        raise SourceError(result["message"])
    for device in result["devices"]:
        if device.get("device_id") == device_id:
            return device
    raise SourceError(
        "Selected camera is disconnected or unavailable. Reconnect the iPhone, enable "
        "Continuity Camera, close other camera apps, then refresh the camera list."
    )


def capture_device(index: int, frames, stop, device_id: str | None = None) -> None:
    capture = None
    try:
        if device_id:
            index = resolve_device(device_id)["index"]
        backend = cv2.CAP_AVFOUNDATION if platform.system() == "Darwin" else cv2.CAP_ANY
        capture = cv2.VideoCapture(index, backend)
        if not capture.isOpened():
            raise SourceError(
                "Camera could not open. In macOS System Settings → Privacy & "
                "Security → Camera, allow the launching Terminal/app. Close other "
                "camera apps; check the device index and Continuity Camera setup."
            )
        if device_id and resolve_device(device_id)["index"] != index:
            raise SourceError("Camera list changed while opening. Refresh and select again.")
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        sequence = 0
        while not stop.is_set():
            ok, frame = capture.read()
            if not ok or frame is None:
                raise SourceError(
                    "Selected camera stopped delivering frames or disconnected. "
                    "Reconnect the iPhone and check Continuity Camera "
                    "and macOS Camera permissions."
                )
            height, width = frame.shape[:2]
            if min(height, width) < 32 or height * width > 33_177_600:
                raise SourceError("Unsupported local camera frame dimensions.")
            if width > 1280:
                frame = cv2.resize(frame, (1280, int(height * 1280 / width)))
            sequence += 1
            packet = ("frame", (frame, time.monotonic(), sequence))
            try:
                frames.put_nowait(packet)
            except queue.Full:
                try:
                    frames.get_nowait()
                except queue.Empty:
                    pass
                try:
                    frames.put_nowait(packet)
                except queue.Full:
                    pass
    except Exception as exc:
        message = (
            str(exc)
            if isinstance(exc, SourceError)
            else "Local camera capture failed. Check device and camera permissions."
        )
        # Bounded error delivery even if the last frame is still queued.
        try:
            frames.get_nowait()
        except queue.Empty:
            pass
        try:
            frames.put(("error", message), timeout=0.2)
        except queue.Full:
            pass
    finally:
        if capture is not None:
            capture.release()


class LocalCameraSource:
    continuous = True
    input_type = "local_camera_avfoundation" if platform.system() == "Darwin" else "local_camera"

    def __init__(self, index: int, timeout: float = 8, device_id: str | None = None):
        if not 0 <= index <= 15:
            raise SourceError("Local camera index must be between 0 and 15.")
        self.timeout, self.epoch = timeout, 0
        self.dropped_frames = self.last_sequence = 0
        self.captured_at = 0.0
        context = mp.get_context("spawn")
        self.frames = context.Queue(maxsize=1)
        self.stop = context.Event()
        self.process = context.Process(
            target=capture_device, args=(index, self.frames, self.stop, device_id), daemon=True
        )
        try:
            self.process.start()
        except (OSError, RuntimeError) as exc:
            self.frames.cancel_join_thread()
            self.frames.close()
            raise SourceError(
                "Cannot start isolated camera capture. Check local process permissions."
            ) from exc

    def read(self):
        try:
            kind, value = self.frames.get(timeout=self.timeout)
        except queue.Empty as exc:
            raise SourceError(
                "Local camera timed out. Grant macOS camera permission, check the device index, "
                "and reconnect the camera; automatic retries are bounded."
            ) from exc
        if kind == "error":
            raise SourceError(value)
        frame, captured, sequence = value
        if time.monotonic() - captured > 2:
            raise SourceError("Local camera delivered an old buffered frame. Reconnecting.")
        self.dropped_frames += max(0, sequence - self.last_sequence - 1)
        self.last_sequence, self.captured_at = sequence, captured
        return frame

    def close(self):
        self.stop.set()
        self.process.join(timeout=0.5)
        if self.process.is_alive():
            self.process.terminate()
            self.process.join(timeout=1)
        if self.process.is_alive():
            self.process.kill()
            self.process.join(timeout=1)
        still_alive = self.process.is_alive()
        self.frames.cancel_join_thread()
        self.frames.close()
        if still_alive:
            raise SourceError(
                "Camera capture process is still closing. "
                "Stop the backend before reopening this device."
            )
