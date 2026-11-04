"""Fintraffic current snapshots and separate TMS measurements. No temporal camera rules.

Provider contract: https://www.digitraffic.fi/en/road-traffic/ and official Swagger.
Network responses are validated at runtime; tests use explicit mock response fixtures.
"""

import hashlib
import ipaddress
import json
import math
import re
import socket
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urlsplit

import cv2
import httpx
import numpy as np

from app.capabilities import capabilities

API = "https://tie.digitraffic.fi"
TERMS = "https://www.digitraffic.fi/en/terms-of-service/"
SOURCE = "https://www.digitraffic.fi/en/road-traffic/"
LICENSE = "https://creativecommons.org/licenses/by/4.0/"
ATTRIBUTION = "Source: Fintraffic / digitraffic.fi, CC BY 4.0. YOLO overlays added by RoadPulse AI."


class ProviderError(RuntimeError):
    pass


def timestamp(value: Any) -> str | None:
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None or dt.timestamp() > time.time() + 120:
            return None
        return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")
    except (ValueError, TypeError, OverflowError):
        return None


def age(value: str | None) -> float | None:
    return (
        max(0, time.time() - datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())
        if value
        else None
    )


def vetted_url(url: str) -> str:
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as exc:
        raise ProviderError("Invalid official provider URL.") from exc
    if (
        parsed.scheme != "https"
        or parsed.username
        or parsed.password
        or port
        or (
            parsed.query
            and not (
                parsed.hostname == "weathercam.digitraffic.fi" and parsed.query == "thumbnail=true"
            )
        )
        or parsed.fragment
    ):
        raise ProviderError("Digitraffic URL must use an unmodified official HTTPS endpoint.")
    api_path = (
        r"/api/(?:weathercam/v1/stations(?:/C\d{5})?(?:/data)?"
        r"|tms/v1/(?:stations(?:/\d+)?(?:/data)?|sensors))"
    )
    if parsed.hostname == "tie.digitraffic.fi" and re.fullmatch(api_path, parsed.path):
        return url
    if parsed.hostname == "weathercam.digitraffic.fi" and re.fullmatch(
        r"/C\d{7}\.jpg", parsed.path
    ):
        return url
    raise ProviderError("Digitraffic host or path is not vetted.")


@dataclass
class Cached:
    body: bytes
    content_type: str
    etag: str | None
    modified: str | None
    next_check: float


class DigitrafficHTTP:
    """One pooled client, serialized requests, bounded LRU, conditional GET, backoff."""

    def __init__(self, user: str = "RoadPulse-AI/local-research", transport=None):
        self.client = httpx.Client(
            headers={
                "Digitraffic-User": user,
                "User-Agent": "RoadPulse-AI/0.1",
                "Accept-Encoding": "gzip",
            },
            timeout=httpx.Timeout(5, connect=5),
            follow_redirects=False,
            trust_env=False,
            limits=httpx.Limits(max_connections=2, max_keepalive_connections=2),
            transport=transport,
        )
        self.custom_transport = transport is not None
        self.lock = threading.RLock()
        self.cache: OrderedDict[str, Cached] = OrderedDict()
        self.failures: dict[str, tuple[int, float]] = {}
        self.last_request = 0.0
        self.retry_after = 0.0

    def get(self, url: str, ttl: float, image: bool = False) -> Cached:
        vetted_url(url)
        with self.lock:
            now = time.monotonic()
            old = self.cache.get(url)
            if old and now < old.next_check:
                self.cache.move_to_end(url)
                return old
            count, retry_at = self.failures.get(url, (0, 0))
            retry_at = max(retry_at, self.retry_after)
            if now < retry_at:
                raise ProviderError("Digitraffic backoff active; waiting before retry.")
            # At most 30 requests/minute even across different resources.
            delay = 2 - (now - self.last_request)
            if delay > 0:
                time.sleep(delay)
            headers = {}
            if old and old.etag:
                headers["If-None-Match"] = old.etag
            if old and old.modified:
                headers["If-Modified-Since"] = old.modified
            retry_delay = min(600, 15 * 2 ** min(count, 5))
            try:
                if not self.custom_transport:
                    addresses = socket.getaddrinfo(urlsplit(url).hostname, 443)
                    if not addresses or any(
                        not ipaddress.ip_address(a[4][0]).is_global for a in addresses
                    ):
                        raise ProviderError(
                            "Official Digitraffic host resolved to a non-public address."
                        )
                self.last_request = time.monotonic()
                started = time.monotonic()
                with self.client.stream("GET", url, headers=headers) as response:
                    if response.status_code == 304:
                        if not old:
                            raise ProviderError("Digitraffic sent 304 without cached content.")
                        old.next_check = time.monotonic() + ttl
                        self.failures.pop(url, None)
                        return old
                    if response.status_code != 200:
                        if response.status_code == 429:
                            try:
                                retry_delay = max(
                                    retry_delay,
                                    min(86400, float(response.headers.get("Retry-After", "60"))),
                                )
                            except ValueError:
                                try:
                                    retry_delay = max(
                                        retry_delay,
                                        min(
                                            86400,
                                            parsedate_to_datetime(
                                                response.headers["Retry-After"]
                                            ).timestamp()
                                            - time.time(),
                                        ),
                                    )
                                except (ValueError, TypeError, KeyError, OverflowError):
                                    retry_delay = max(retry_delay, 60)
                        if response.status_code == 429:
                            self.retry_after = time.monotonic() + retry_delay
                        raise ProviderError(
                            f"Digitraffic HTTP {response.status_code}; source unavailable. "
                            "No substitute imagery."
                        )
                    mime = response.headers.get("Content-Type", "").split(";", 1)[0].lower()
                    if (image and mime != "image/jpeg") or (not image and "json" not in mime):
                        raise ProviderError("Digitraffic returned an unexpected content type.")
                    maximum = 8_000_000 if image else 24_000_000
                    body = bytearray()
                    for chunk in response.iter_bytes(chunk_size=65536):
                        if time.monotonic() - started > 8:
                            raise ProviderError("Digitraffic response exceeded time budget.")
                        body.extend(chunk)
                        if len(body) > maximum:
                            raise ProviderError("Digitraffic response exceeds size limit.")
                    item = Cached(
                        bytes(body),
                        mime,
                        response.headers.get("ETag"),
                        response.headers.get("Last-Modified"),
                        time.monotonic() + ttl,
                    )
                self.cache[url] = item
                self.cache.move_to_end(url)
                # Keep at most 32 resources and 40 MB of decoded HTTP payloads in memory.
                while (
                    len(self.cache) > 32
                    or sum(len(c.body) for c in self.cache.values()) > 40_000_000
                ):
                    self.cache.popitem(last=False)
                self.failures.pop(url, None)
                return item
            except (httpx.HTTPError, OSError, ProviderError) as exc:
                if len(self.failures) >= 32:
                    self.failures.pop(next(iter(self.failures)))
                self.failures[url] = (count + 1, time.monotonic() + retry_delay)
                if isinstance(exc, ProviderError):
                    raise
                raise ProviderError(
                    "Digitraffic network/TLS request failed; waiting before retry."
                ) from None

    def json(self, path: str, ttl: float = 21600) -> dict:
        try:
            data = json.loads(self.get(API + path, ttl).body)
        except (ValueError, TypeError) as exc:
            raise ProviderError("Digitraffic JSON could not be decoded.") from exc
        if not isinstance(data, dict):
            raise ProviderError("Digitraffic response schema is not an object.")
        return data

    def close(self):
        self.client.close()


def stations(payload: dict) -> list[dict]:
    if payload.get("type") != "FeatureCollection" or not isinstance(payload.get("features"), list):
        raise ProviderError("Unsupported Digitraffic station GeoJSON schema.")
    rows = []
    for feature in payload["features"]:
        if not isinstance(feature, dict):
            raise ProviderError("Malformed Digitraffic GeoJSON feature.")
        props = feature.get("properties")
        geometry = feature.get("geometry")
        if not isinstance(props, dict) or not isinstance(geometry, dict):
            continue
        coords = geometry.get("coordinates", [])
        if not isinstance(coords, list):
            continue
        if len(coords) < 2 or not all(
            isinstance(n, (int, float)) and math.isfinite(n) for n in coords[:2]
        ):
            continue
        if not (-180 <= coords[0] <= 180 and -90 <= coords[1] <= 90):
            continue
        rows.append(
            {
                **props,
                "id": str(props.get("id", feature.get("id", ""))),
                "longitude": coords[0],
                "latitude": coords[1],
            }
        )
    return rows


def usable(props: dict, *, summary: bool = False) -> bool | None:
    """Tri-state metadata evidence, not a claim that an image is available.

    Missing state is unknown (observed in operator's C01504 response), never
    treated as OK. Unknown candidates must pass the JPEG/timestamp gate in read.
    Explicit non-OK or non-collecting metadata is not overridden by an old JPEG.
    """
    state = props.get("state")
    collecting = props.get("collectionStatus")
    if state is not None and not isinstance(state, str):
        raise ProviderError("Unsupported camera state type; inspect official metadata schema.")
    if collecting is not None and not isinstance(collecting, str):
        raise ProviderError("Unsupported camera collectionStatus type.")
    if state is not None and state != "OK":
        return False
    if summary and collecting is None:
        return None  # Simplified directory is not sufficient; inspect detailed metadata.
    if collecting != "GATHERING":
        return False
    return True if state == "OK" else None


def presets(feature: dict) -> list[dict]:
    props = feature.get("properties", {})
    if not isinstance(props, dict):
        raise ProviderError("Malformed camera station properties.")
    if feature.get("type") != "Feature" or usable(props) is False:
        return []
    station_id = str(props.get("id", feature.get("id", "")))
    if not re.fullmatch(r"C\d{5}", station_id):
        raise ProviderError("Invalid official camera station ID.")
    geometry = feature.get("geometry") or {}
    if not isinstance(geometry, dict):
        raise ProviderError("Invalid camera geometry.")
    coords = geometry.get("coordinates", [])
    if not isinstance(coords, list):
        coords = []
    if not isinstance(props.get("presets", []), list):
        raise ProviderError("Malformed camera presets array.")
    result = []
    for preset in props.get("presets", []):
        if not isinstance(preset, dict):
            raise ProviderError("Malformed camera preset.")
        ident = str(preset.get("id", ""))
        if preset.get("inCollection") is not True or not re.fullmatch(r"C\d{7}", ident):
            continue
        image = preset.get("imageUrl", "")
        vetted_url(image)
        if urlsplit(image).path != f"/{ident}.jpg":
            raise ProviderError("Preset ID and official image URL disagree.")
        result.append(
            {
                "id": "digitraffic-" + ident,
                "preset_id": ident,
                "station_id": station_id,
                "name": (
                    f"{props.get('name', station_id)} · {preset.get('presentationName', ident)}"
                ),
                "orientation": preset.get("presentationName", ""),
                "mode": "SNAPSHOT",
                "capabilities": capabilities("digitraffic", True),
                "source_type": "digitraffic",
                "provider": "Fintraffic / Digitraffic",
                "region": str(props.get("municipality", "Finland")),
                "latitude": coords[1] if len(coords) > 1 else None,
                "longitude": coords[0] if coords else None,
                "source_page": SOURCE,
                "terms_url": TERMS,
                "license_url": LICENSE,
                "license_status": "CC BY 4.0",
                "attribution": ATTRIBUTION,
                "analysis_authorized": True,
                "redisplay_authorized": True,
                "permission_notes": (
                    "Fintraffic CC BY 4.0 terms; attribution and overlay modifications displayed."
                ),
                "permission_checked": "2026-11-01",
                "enabled": True,
                "metadata_state_verified": usable(props) is True,
                "availability_note": "Fresh official JPEG/timestamp validation required",
                "image_url": image,
            }
        )
    return result


class DigitrafficService:
    def __init__(
        self, user: str = "RoadPulse-AI/local-research", http: DigitrafficHTTP | None = None
    ):
        self.http = http or DigitrafficHTTP(user)
        self.lock = threading.RLock()
        self.resolved: OrderedDict[str, dict] = OrderedDict()
        self.station_checks: OrderedDict[str, dict] = OrderedDict()
        self.discovery_lock = threading.Lock()
        self.alternatives_cache: OrderedDict[str, tuple[float, list[dict]]] = OrderedDict()

    def camera_stations(self) -> list[dict]:
        rows = stations(self.http.json("/api/weathercam/v1/stations"))
        return [
            {
                "id": r["id"],
                "name": r.get("name", r["id"]),
                "latitude": r["latitude"],
                "longitude": r["longitude"],
                "available": usable(r, summary=True),
                "state": r.get("state"),
                "collection_status": r.get("collectionStatus"),
                "region": str(r.get("municipality", "Finland")),
                "availability_reason": "Metadata incomplete; detail/image checks required"
                if usable(r, summary=True) is None
                else None
                if usable(r, summary=True)
                else f"state={r.get('state')}, collectionStatus={r.get('collectionStatus')}",
            }
            for r in rows
            if re.fullmatch(r"C\d{5}", r["id"])
        ]

    def camera_presets(self, station: str) -> list[dict]:
        if not re.fullmatch(r"C\d{5}", station):
            raise ProviderError("Invalid Digitraffic camera station ID.")
        detail = self.http.json(f"/api/weathercam/v1/stations/{station}", 600)
        items = presets(detail)
        props = detail.get("properties", {})
        reported = props.get("presets") or []
        if not isinstance(reported, list) or any(not isinstance(p, dict) for p in reported):
            raise ProviderError("Malformed station preset metadata.")
        with self.lock:
            self.station_checks[station] = {
                "state": props.get("state"),
                "state_type": type(props.get("state")).__name__,
                "state_present": "state" in props,
                "collectionStatus": props.get("collectionStatus"),
                "reported_presets": len(reported),
                "in_collection": sum(p.get("inCollection") is True for p in reported),
                "usable_presets": [c["preset_id"] for c in items],
            }
            while len(self.station_checks) > 128:
                self.station_checks.popitem(last=False)
            for key in list(self.resolved):
                if self.resolved[key]["station_id"] == station:
                    del self.resolved[key]
            for item in items:
                self.resolved[item["id"]] = item
                self.resolved.move_to_end(item["id"])
            while len(self.resolved) > 128:
                self.resolved.popitem(last=False)
        return [self.public(item) for item in items]

    @staticmethod
    def public(item: dict) -> dict:
        return {
            **{k: v for k, v in item.items() if k != "image_url"},
            "public_image_url": item["image_url"],
        }

    def cameras(self) -> list[dict]:
        with self.lock:
            return [self.public(c) for c in self.resolved.values()]

    def camera(self, ident: str) -> dict:
        with self.lock:
            item = self.resolved.get(ident)
            if not item:
                raise ProviderError("Browse and select an available Digitraffic preset first.")
            return dict(item)

    def discover(
        self,
        station: str | None = None,
        preset: str | None = None,
        max_stations: int = 6,
        max_images: int = 3,
        exclude_station: str | None = None,
    ):
        """Bounded current discovery. Yield fresh decoded images, never a synthetic fallback."""
        directory = self.camera_stations()
        candidates = [
            r for r in directory if r["available"] is not False and r["id"] != exclude_station
        ]
        if station:
            candidates.sort(key=lambda r: r["id"] != station)
        diagnostics: list[dict] = []
        self.discovery_diagnostics = diagnostics
        if not candidates:
            states = sorted({str((r.get("state"), r.get("collection_status"))) for r in directory})
            raise ProviderError(
                f"No stations pass collection checks. Observed state/status values: {states}"
            )
        images = 0
        for row in candidates[: max(1, min(max_stations, 12))]:
            try:
                choices = self.camera_presets(row["id"])
                if preset:
                    choices.sort(key=lambda c: c["preset_id"] != preset)
                if not choices:
                    diagnostics.append(
                        {
                            "station_id": row["id"],
                            "result": "No in-collection presets",
                            "metadata": self.station_checks.get(row["id"], {}),
                        }
                    )
                for choice in choices[:2]:
                    if images >= max(1, min(max_images, 5)):
                        return
                    images += 1
                    try:
                        camera = self.camera(choice["id"])
                        source = DigitrafficSnapshot(self, camera)
                        frame = source.read()
                        image_age = age(source.source_timestamp)
                        if frame is None or image_age is None or image_age > 1800:
                            raise ProviderError(
                                "Image missing, timestamp unknown or older than 30 minutes"
                            )
                        diagnostics.append(
                            {
                                "station_id": row["id"],
                                "preset_id": choice["preset_id"],
                                "result": "Fresh JPEG decoded",
                            }
                        )
                        yield camera, source, frame
                    except ProviderError as exc:
                        diagnostics.append(
                            {
                                "station_id": row["id"],
                                "preset_id": choice["preset_id"],
                                "result": str(exc),
                            }
                        )
            except ProviderError as exc:
                diagnostics.append({"station_id": row["id"], "result": str(exc)})

    def verified_alternatives(self, exclude: str = "") -> list[dict]:
        """User-requested bounded image probes, cached; never opens every camera."""
        if exclude and not re.fullmatch(r"C\d{5}", exclude):
            raise ProviderError("Invalid excluded station ID.")
        with self.discovery_lock:
            cached = self.alternatives_cache.get(exclude)
            if cached and time.monotonic() - cached[0] < 60:
                return cached[1]
            result = []
            for camera, source, _ in self.discover(exclude_station=exclude):
                result.append(
                    {
                        **self.public(camera),
                        "image_verified_at": datetime.now(UTC).isoformat(),
                        "source_timestamp": source.source_timestamp,
                        "timestamp_kind": source.timestamp_kind,
                    }
                )
                if len(result) >= 2:
                    break
            self.alternatives_cache[exclude] = (time.monotonic(), result)
            while len(self.alternatives_cache) > 8:
                self.alternatives_cache.popitem(last=False)
            return result

    def tms_stations(self) -> list[dict]:
        return [
            {
                "id": r["id"],
                "name": r.get("name", r["id"]),
                "latitude": r["latitude"],
                "longitude": r["longitude"],
                "collection_status": r.get("collectionStatus"),
            }
            for r in stations(self.http.json("/api/tms/v1/stations"))
            if r["id"].isdigit()
        ]

    def tms(self, station: str) -> dict:
        if not station.isdigit() or len(station) > 12:
            raise ProviderError("Invalid TMS station ID.")
        directory = self.tms_stations()
        selected = next((r for r in directory if r["id"] == station), None)
        if not selected:
            raise ProviderError("TMS station is not in the official directory.")
        definitions = self.http.json("/api/tms/v1/sensors")
        data = self.http.json("/api/tms/v1/stations/data", 60)
        return {
            "station": selected,
            "measurements": tms_measurements(data, definitions, station)
            if selected["collection_status"] == "GATHERING"
            else [],
            "attribution": ATTRIBUTION,
            "source": SOURCE,
            "license_url": LICENSE,
            "note": (
                "Separate roadside TMS station selected by the operator; "
                "not camera-derived or automatically matched to this camera."
            ),
        }


def tms_measurements(payload: dict, definitions: dict, station: str) -> list[dict]:
    rows = payload.get("stations")
    sensors = definitions.get("sensors")
    if not isinstance(rows, list) or not isinstance(sensors, list):
        raise ProviderError("Unsupported TMS data or sensor-definition schema.")
    lookup = {s["id"]: s for s in sensors}
    result = []
    for row in rows:
        if str(row.get("id")) != station:
            continue
        for value in row.get("sensorValues", []):
            definition = lookup.get(value.get("id"), {})
            unit = value.get("sensorUnit") or definition.get("unit", "")
            number = value.get("sensorValue")
            measured = timestamp(value.get("measuredTime") or row.get("measuredTime"))
            if (
                not measured
                or not isinstance(number, (int, float))
                or isinstance(number, bool)
                or not math.isfinite(number)
                or number < 0
            ):
                continue
            if unit not in {"km/h", "kpl/h", "kpl", "kpl/5min"}:
                continue
            name = value.get("name") or definition.get("name", str(value.get("id")))
            direction = re.search(r"SUUNTA(\d+)", name)
            window = re.search(r"(\d+)MIN", name)
            result.append(
                {
                    "sensor_id": value.get("id"),
                    "direction": direction.group(1) if direction else None,
                    "window_minutes_from_sensor_name": int(window.group(1)) if window else None,
                    "name": name,
                    "value": number,
                    "unit": unit,
                    "measured_at": measured,
                    "age_seconds": age(measured),
                    "stale": (age(measured) or 0) > 300,
                    "definition": definition,
                    "origin": "Official Fintraffic roadside TMS, not YOLO",
                }
            )
    return result


class DigitrafficSnapshot:
    continuous = False
    input_type = "digitraffic_snapshot"

    def __init__(self, service: DigitrafficService, camera: dict):
        self.service, self.camera = service, camera
        self.epoch = 0
        self.digest: bytes | None = None
        self.last_item: Cached | None = None
        self.source_timestamp: str | None = None
        self.timestamp_kind = "unknown"
        self.next_refresh: str | None = None

    def read(self) -> np.ndarray | None:
        detail = self.service.http.json(
            f"/api/weathercam/v1/stations/{self.camera['station_id']}", 600
        )
        if not any(c["id"] == self.camera["id"] for c in presets(detail)):
            raise ProviderError("Selected preset is no longer reported in collection.")
        item = self.service.http.get(self.camera["image_url"], 600, image=True)
        if item is self.last_item:
            return None
        self.last_item = item
        digest = hashlib.sha256(item.body).digest()
        if digest == self.digest:
            return None
        frame = cv2.imdecode(np.frombuffer(item.body, np.uint8), cv2.IMREAD_COLOR)
        if (
            frame is None
            or min(frame.shape[:2]) < 32
            or frame.shape[0] * frame.shape[1] > 33_177_600
        ):
            raise ProviderError("Digitraffic JPEG decoding or dimensions invalid.")
        # Obtain capture time from the selected preset's latest-data record. Never use request time.
        data = self.service.http.json(
            f"/api/weathercam/v1/stations/{self.camera['station_id']}/data", 600
        )
        records = data.get("presets")
        if not isinstance(records, list) or any(not isinstance(r, dict) for r in records):
            raise ProviderError("Unsupported camera latest-data preset schema.")
        self.source_timestamp = next(
            (
                timestamp(r.get("measuredTime"))
                for r in records
                if r.get("id") == self.camera["preset_id"]
            ),
            None,
        )
        self.timestamp_kind = "provider measuredTime" if self.source_timestamp else "unknown"
        if not self.source_timestamp and item.modified:
            try:
                self.source_timestamp = timestamp(parsedate_to_datetime(item.modified).isoformat())
                self.timestamp_kind = (
                    "HTTP Last-Modified (image update, not guaranteed capture time)"
                )
            except (ValueError, TypeError, OverflowError):
                pass
        image_age = age(self.source_timestamp)
        if image_age is None or image_age > 1800:
            raise ProviderError(
                "Camera image timestamp is missing or older than 30 minutes. "
                "Choose a verified alternative; no substitute image is used."
            )
        self.digest = digest
        if self.source_timestamp:
            dt = datetime.fromisoformat(self.source_timestamp.replace("Z", "+00:00"))
            self.next_refresh = datetime.fromtimestamp(dt.timestamp() + 600, UTC).isoformat()
        h, w = frame.shape[:2]
        return cv2.resize(frame, (1280, int(h * 1280 / w))) if w > 1280 else frame

    def close(self):
        pass
