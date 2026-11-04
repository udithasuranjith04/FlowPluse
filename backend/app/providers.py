"""Metadata discovery only. A candidate never grants camera-processing permission."""

import ipaddress
import json
import socket
from dataclasses import dataclass, field
from typing import Protocol
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, build_opener


@dataclass(frozen=True)
class CameraCandidate:
    id: str
    name: str
    provider: str
    region: str
    snapshot_url: str = field(repr=False)
    video_url: str = field(repr=False)
    viewer_url: str = field(repr=False)
    snapshot_interval_seconds: float | None
    in_service: bool
    source_page: str
    terms_url: str
    analysis_authorized: bool = False
    redisplay_authorized: bool = False


class ProviderAdapter(Protocol):
    def catalog_url(self, district: int) -> str: ...
    def parse(self, payload: dict) -> list[CameraCandidate]: ...


def media_link(value) -> str:
    if not isinstance(value, str):
        return ""
    try:
        url = urlsplit(value)
        if url.scheme in {"https", "http", "rtsp", "rtsps"} and url.hostname:
            return value
    except ValueError:
        pass
    return ""


class CaltransProvider:
    """CWWP2 schema verified against its official JSON example and district 1 data."""

    def catalog_url(self, district: int) -> str:
        if not 1 <= district <= 12:
            raise ValueError("Caltrans district must be 1–12")
        return f"https://cwwp2.dot.ca.gov/data/d{district}/cctv/cctvStatusD{district:02d}.json"

    def parse(self, payload: dict) -> list[CameraCandidate]:
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
            raise ValueError("Unsupported Caltrans catalog schema: expected data array")
        candidates = []
        for row in payload["data"]:
            if not isinstance(row, dict) or not isinstance(row.get("cctv"), dict):
                raise ValueError("Unsupported Caltrans catalog row")
            camera = row["cctv"]
            location, images = camera.get("location", {}), camera.get("imageData", {})
            still = images.get("static", {})
            video = media_link(images.get("streamingVideoURL", ""))
            viewer = ""
            if urlsplit(video).path.lower().endswith((".html", ".htm", ".aspx")):
                viewer, video = video, ""
            interval: float | None
            try:
                interval = float(still.get("currentImageUpdateFrequency", 0)) * 60
                # Official field description specifies minutes, not seconds.
                interval = interval if 0 < interval <= 86400 else None
            except (TypeError, ValueError):
                interval = None
            candidates.append(
                CameraCandidate(
                    id=f"caltrans-d{location.get('district', '')}-{camera.get('index', '')}",
                    name=str(location.get("locationName", "Unnamed camera")),
                    provider="Caltrans CWWP2",
                    region=str(location.get("county", "")),
                    snapshot_url=media_link(still.get("currentImageURL", "")),
                    video_url=video,
                    viewer_url=viewer,
                    snapshot_interval_seconds=interval,
                    in_service=str(camera.get("inService", "")).lower() == "true",
                    source_page="https://cwwp2.dot.ca.gov/closed-circuit-television-cameras.html",
                    terms_url="https://dot.ca.gov/conditions-of-use",
                )
            )
        return candidates


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch_catalog(provider: ProviderAdapter, district: int) -> dict:
    """Explicit, bounded metadata request. Never fetch images/video or follow redirects."""
    url = provider.catalog_url(district)
    host = urlsplit(url).hostname
    addresses = socket.getaddrinfo(host, 443)
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise ValueError("Provider catalog must resolve to public addresses")
    with build_opener(ProxyHandler({}), NoRedirect()).open(url, timeout=5) as response:
        payload = response.read(8_000_001)
    if len(payload) > 8_000_000:
        raise ValueError("Provider catalog exceeds 8 MB")
    return json.loads(payload)
