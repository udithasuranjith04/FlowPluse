import ipaddress
import socket
import time
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

import cv2
import numpy as np

from app.config import Settings
from app.synthetic import render_frame


class SourceError(RuntimeError):
    pass


def validate_source(settings: Settings) -> str:
    if not (settings.camera_analysis_authorized and settings.camera_redisplay_authorized):
        raise SourceError("Analysis and redisplay permission must both be recorded in .env.")
    if not settings.camera_permission_notes or not settings.camera_permission_checked:
        raise SourceError("Record permission evidence and the date it was checked in .env.")
    if settings.camera_mode == "replay":
        path = Path(settings.replay_path).expanduser()
        if not path.is_file():
            raise SourceError("Configured replay file is unavailable.")
        return str(path)
    try:
        url = urlsplit(settings.camera_url)
        port = url.port
    except ValueError as exc:
        raise SourceError("Invalid source URL or port.") from exc
    if url.scheme not in {"https", "http", "rtsp", "rtsps"} or not url.hostname:
        raise SourceError("Source must be an HTTP(S) or RTSP(S) video URL.")
    if settings.camera_mode == "snapshot" and url.scheme not in {"http", "https"}:
        raise SourceError("Snapshots require an HTTP(S) JPEG or PNG endpoint.")
    hosts = [h.strip().lower() for h in settings.camera_allowed_hosts.split(",")]
    if url.hostname not in hosts:
        raise SourceError("Source hostname must be explicitly allowlisted in .env.")
    try:
        addresses = socket.getaddrinfo(
            url.hostname,
            port or (80 if url.scheme == "http" else 554 if url.scheme.startswith("rtsp") else 443),
        )
    except OSError as exc:
        raise SourceError("Source hostname could not be resolved.") from exc
    if not addresses:
        raise SourceError("Source hostname returned no addresses.")
    if not settings.camera_allow_private:
        if any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
            raise SourceError(
                "Private-network cameras require explicit local configuration opt-in."
            )
    return settings.camera_url


class CheckedRedirects(HTTPRedirectHandler):
    def __init__(self, settings: Settings):
        self.settings = settings

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_source(self.settings.model_copy(update={"camera_url": newurl}))
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def open_http(target: str, settings: Settings):
    # Recheck on each snapshot and each redirect. No ambient system proxy is needed.
    from urllib.request import ProxyHandler

    validate_source(settings.model_copy(update={"camera_url": target}))
    try:
        return build_opener(ProxyHandler({}), CheckedRedirects(settings)).open(
            Request(
                target, headers={"User-Agent": "RoadPulse-AI/0.1", "Cache-Control": "no-cache"}
            ),
            timeout=5,
        )
    except SourceError:
        raise
    except (OSError, ValueError) as exc:
        raise SourceError(
            "HTTP source unavailable. Check access, TLS, expiry and network."
        ) from exc


def input_type(content_type: str, prefix: bytes = b"") -> str:
    mime = content_type.split(";", 1)[0].strip().lower()
    if mime in {"image/jpeg", "image/png"} or prefix.startswith((b"\xff\xd8\xff", b"\x89PNG")):
        return "snapshot"
    if mime == "multipart/x-mixed-replace":
        return "mjpeg"
    if "mpegurl" in mime or prefix.lstrip().startswith(b"#EXTM3U"):
        return "hls"
    if mime.startswith("video/"):
        return "http_video"
    if mime in {"text/html", "application/json", "text/plain"}:
        raise SourceError("Endpoint is a page or metadata, not video. Supply a direct stream URL.")
    return "http_video_unconfirmed"


class SyntheticSource:
    continuous = True
    input_type = "synthetic"

    def __init__(self):
        self.started = time.monotonic()
        self.epoch = 0

    def read(self) -> np.ndarray | None:
        elapsed = time.monotonic() - self.started
        self.epoch = int(elapsed / 80)
        return render_frame(elapsed)

    def close(self) -> None:
        pass


class VideoSource:
    """OpenCV's FFmpeg backend, bounded open/read timeout; never logs upstream URLs."""

    continuous = True

    def __init__(
        self,
        target: str,
        replay: bool = False,
        settings: Settings | None = None,
        loop: bool = True,
    ):
        self.input_type = "local_video" if replay else "rtsp"
        if not replay and target.startswith(("http://", "https://")) and settings is not None:
            with open_http(target, settings) as response:
                self.input_type = input_type(
                    response.headers.get("Content-Type", ""), response.read(16)
                )
            if self.input_type == "snapshot":
                raise SourceError(
                    "Still-image endpoint detected. Set ROADPULSE_CAMERA_MODE=snapshot; "
                    "tracking is disabled."
                )
        # FFmpeg logging is disabled globally at process startup; never expose signed URLs.
        self.capture = cv2.VideoCapture(
            target,
            cv2.CAP_FFMPEG,
            [
                cv2.CAP_PROP_OPEN_TIMEOUT_MSEC,
                5000,
                cv2.CAP_PROP_READ_TIMEOUT_MSEC,
                5000,
            ],
        )
        if not self.capture.isOpened():
            self.capture.release()
            raise SourceError(
                "Cannot open source. Verify permission, URL expiry, format and network."
            )
        self.replay = replay
        self.loop = loop
        self.fps = min(120.0, max(1.0, self.capture.get(cv2.CAP_PROP_FPS) or 25))
        self.next_frame = time.monotonic()
        self.epoch = 0

    def read(self) -> np.ndarray | None:
        if self.replay:
            delay = self.next_frame - time.monotonic()
            if delay > 0:
                time.sleep(min(delay, 1))
            self.next_frame = max(self.next_frame + 1 / self.fps, time.monotonic())
        success, frame = self.capture.read()
        if not success and self.replay and self.loop:
            self.capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
            self.epoch += 1
            success, frame = self.capture.read()
        if not success or frame is None or frame.size == 0:
            return None
        height, width = frame.shape[:2]
        if height < 32 or width < 32 or height * width > 33_177_600:
            raise SourceError("Source frame dimensions are unsupported.")
        scale = min(1.0, 1280 / width)
        return cv2.resize(frame, (int(width * scale), int(height * scale))) if scale < 1 else frame

    def close(self) -> None:
        self.capture.release()


class SnapshotSource:
    """Bounded HTTP image fetch; never claims temporal tracking across snapshots."""

    continuous = False
    input_type = "snapshot"

    def __init__(self, target: str, settings: Settings):
        self.target, self.settings = target, settings
        self.epoch = 0

    def read(self) -> np.ndarray | None:
        with open_http(self.target, self.settings) as response:
            payload = response.read(8_000_001)
            if len(payload) > 8_000_000:
                raise SourceError("Snapshot exceeds the 8 MB response limit.")
            if input_type(response.headers.get("Content-Type", ""), payload[:16]) != "snapshot":
                raise SourceError(
                    "Snapshot source must return a JPEG or PNG image, not video or a viewing page."
                )
        frame = cv2.imdecode(np.frombuffer(payload, np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            raise SourceError("Snapshot could not be decoded as JPEG or PNG.")
        height, width = frame.shape[:2]
        if height < 32 or width < 32 or height * width > 33_177_600:
            raise SourceError("Snapshot frame dimensions are unsupported.")
        scale = min(1.0, 1280 / width)
        return cv2.resize(frame, (int(width * scale), int(height * scale))) if scale < 1 else frame

    def close(self) -> None:
        pass
