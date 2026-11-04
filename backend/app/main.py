import os

# Set before importing OpenCV/FFmpeg; native decoder errors may otherwise print signed URLs.
os.environ["OPENCV_FFMPEG_LOGLEVEL"] = "-8"
os.environ["OPENCV_LOG_LEVEL"] = "SILENT"

import asyncio
import csv
import io
import json
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.config import Settings
from app.digitraffic import ProviderError
from app.local_camera import list_devices
from app.pipeline import Pipeline
from app.schemas import ReviewUpdate, ZoneConfig
from app.sources import SourceError
from app.storage import Store

ObservationType = Literal[
    "potential_stopped_vehicle", "congestion_buildup", "extended_dwell", "possible_queue_buildup"
]


class LocalCameraRequest(BaseModel):
    # Reject retired testing-only options rather than silently treating a
    # prerecorded feed as a real live shift.
    model_config = ConfigDict(extra="forbid")

    device_index: int = Field(default=0, ge=0, le=15)
    device_id: str | None = Field(default=None, min_length=1, max_length=512)
    analysis_authorized: bool = False
    redisplay_authorized: bool = False


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        store = Store(settings.db_path)
        pipeline = Pipeline(settings, store)
        app.state.store, app.state.pipeline = store, pipeline
        if settings.autostart:
            camera = (
                settings.camera_id
                if settings.camera_url or settings.replay_path or settings.camera_mode != "replay"
                else "demo"
            )
            try:
                await asyncio.to_thread(pipeline.activate, camera)
            except SourceError as exc:
                pipeline.camera_id = settings.camera_id
                pipeline.log("Configured source could not start; synthetic replay is available.")
                pipeline.error = str(exc)

        async def purge_evidence():
            while True:
                await asyncio.to_thread(pipeline.evidence.purge)
                await asyncio.sleep(60)

        cleanup = asyncio.create_task(purge_evidence())
        yield
        cleanup.cancel()
        with suppress(asyncio.CancelledError):
            await cleanup
        try:
            await asyncio.to_thread(pipeline.stop)
        finally:
            pipeline.digitraffic.http.close()
            store.close()

    app = FastAPI(title="FlowPulse AI", version="1.0.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.origins,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type"],
    )
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=[x.strip() for x in settings.allowed_hosts.split(",")]
    )

    @app.middleware("http")
    async def local_boundary(request: Request, call_next):
        origin = request.headers.get("origin")
        if (
            origin
            and origin not in settings.origins
            and origin != str(request.base_url).rstrip("/")
        ):
            return JSONResponse(
                {
                    "error": {
                        "code": "origin_forbidden",
                        "message": "Origin is not configured for local access.",
                    }
                },
                status_code=403,
            )
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        return JSONResponse(
            {"error": {"code": f"http_{exc.status_code}", "message": str(exc.detail)}},
            status_code=exc.status_code,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        # Never echo validation input: it may contain user-supplied secrets.
        return JSONResponse(
            {
                "error": {
                    "code": "validation_error",
                    "message": "Invalid request.",
                    "details": [
                        {"field": ".".join(map(str, e["loc"])), "message": e["msg"]}
                        for e in exc.errors()
                    ],
                }
            },
            status_code=422,
        )

    def pipeline() -> Pipeline:
        return app.state.pipeline

    def store() -> Store:
        return app.state.store

    def camera_exists(camera_id: str) -> None:
        if camera_id not in {c["id"] for c in pipeline().cameras()}:
            raise HTTPException(404, "Camera not found.")

    @app.get("/api/health")
    def health():
        return {"status": "ok", "version": "1.0.0"}

    @app.get("/api/system/status")
    def status():
        return pipeline().status()

    @app.get("/api/config/public")
    def public_config():
        return {
            "name": "FlowPulse AI",
            "version": "1.0.0",
            "local_only": True,
            "digitraffic_enabled": settings.digitraffic_enabled,
            "evidence_enabled": settings.save_evidence,
            "evidence_ttl_hours": settings.evidence_ttl_hours,
            "model_license": "AGPL-3.0",
            "upstream_urls": "Environment only",
            "disclaimer": "Research demo. Observations require human review.",
        }

    @app.get("/api/cameras")
    def cameras():
        return pipeline().cameras()

    def digitraffic():
        if not settings.digitraffic_enabled:
            raise HTTPException(
                409,
                "Enable ROADPULSE_DIGITRAFFIC_ENABLED in .env to browse official CC BY 4.0 data.",
            )
        return pipeline().digitraffic

    async def provider_call(method, *args):
        try:
            return await asyncio.to_thread(method, *args)
        except ProviderError as exc:
            raise HTTPException(503, str(exc)) from exc
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            raise HTTPException(
                503, "Digitraffic response schema is incompatible. Check current official Swagger."
            ) from exc

    @app.get("/api/providers/digitraffic/stations")
    async def provider_stations():
        return await provider_call(digitraffic().camera_stations)

    @app.get("/api/providers/digitraffic/alternatives")
    async def provider_alternatives(exclude: str = ""):
        return await provider_call(digitraffic().verified_alternatives, exclude)

    @app.get("/api/providers/digitraffic/stations/{station}/presets")
    async def provider_presets(station: str):
        service = digitraffic()
        items = await provider_call(service.camera_presets, station)
        if not items:
            check = service.station_checks.get(station, {})
            raise HTTPException(
                409,
                f"No usable presets: state={check.get('state')}, "
                f"collectionStatus={check.get('collectionStatus')}, "
                f"inCollection={check.get('in_collection')}/{check.get('reported_presets')}. "
                "Choose another station; no substitute footage is used.",
            )
        return items

    @app.get("/api/providers/digitraffic/presets/{ident}/thumbnail.jpg")
    async def provider_thumbnail(ident: str):
        service = digitraffic()

        async def load():
            camera = service.camera(ident)
            return await asyncio.to_thread(
                service.http.get, camera["image_url"] + "?thumbnail=true", 600, True
            )

        try:
            item = await load()
            return Response(
                item.body,
                media_type="image/jpeg",
                headers={"Cache-Control": "private, max-age=600"},
            )
        except ProviderError as exc:
            raise HTTPException(503, str(exc)) from exc

    @app.get("/api/providers/digitraffic/tms/stations")
    async def provider_tms_stations():
        return await provider_call(digitraffic().tms_stations)

    @app.get("/api/providers/digitraffic/tms/{station}")
    async def provider_tms(station: str):
        return await provider_call(digitraffic().tms, station)

    @app.post("/api/cameras/{camera_id}/activate")
    async def activate(camera_id: str):
        camera_exists(camera_id)
        try:
            await asyncio.to_thread(pipeline().activate, camera_id)
        except (SourceError, ProviderError) as exc:
            raise HTTPException(409, str(exc)) from exc
        return pipeline().status()

    @app.get("/api/local-camera/devices")
    async def local_devices():
        return await asyncio.to_thread(list_devices)

    @app.post("/api/local-camera/activate")
    async def local_activate(consent: LocalCameraRequest):
        if not (consent.analysis_authorized and consent.redisplay_authorized):
            raise HTTPException(
                409,
                "Confirm you control this camera and permit local analysis and dashboard display.",
            )
        try:
            await asyncio.to_thread(
                pipeline().activate_local,
                consent.device_index,
                False,
                consent.device_id,
            )
        except SourceError as exc:
            raise HTTPException(409, str(exc)) from exc
        return pipeline().status()

    @app.post("/api/local-camera/preview")
    async def local_preview(consent: LocalCameraRequest):
        if not (consent.analysis_authorized and consent.redisplay_authorized):
            raise HTTPException(
                409, "Preview requires permission to access and process your camera."
            )
        try:
            await asyncio.to_thread(
                pipeline().activate_local,
                consent.device_index,
                True,
                consent.device_id,
            )
        except SourceError as exc:
            raise HTTPException(409, str(exc)) from exc
        return pipeline().status()

    class ShiftMemoryConsent(BaseModel):
        enabled: bool

    @app.get("/api/privacy/shift-memory")
    def get_shift_memory():
        active = store().shift_memory_enabled()
        camera_id = pipeline().camera_id
        region = pipeline().config.staff_only_region
        return {
            "enabled": active,
            "saved_shifts": store().saved_shifts(camera_id, region),
            "retention_days": 30,
            "minimum_samples": 300,
            "minimum_duration_seconds": 240,
        }

    @app.put("/api/privacy/shift-memory")
    def change_shift_memory(consent: ShiftMemoryConsent):
        store().set_shift_memory(consent.enabled)
        return get_shift_memory()

    @app.delete("/api/privacy/shift-memory")
    def delete_shift_memory():
        store().set_shift_memory(False)
        return get_shift_memory()

    @app.post("/api/system/pause")
    async def pause():
        try:
            await asyncio.to_thread(pipeline().pause)
        except SourceError as exc:
            raise HTTPException(409, str(exc)) from exc
        return pipeline().status()

    @app.post("/api/system/resume")
    async def resume():
        try:
            await asyncio.to_thread(pipeline().resume)
        except (SourceError, ProviderError) as exc:
            raise HTTPException(409, str(exc)) from exc
        return pipeline().status()

    @app.post("/api/system/stop")
    async def stop():
        try:
            await asyncio.to_thread(pipeline().stop)
        except (SourceError, ProviderError) as exc:
            raise HTTPException(409, str(exc)) from exc
        return pipeline().status()

    @app.get("/api/cameras/{camera_id}/zones")
    def zones(camera_id: str):
        camera_exists(camera_id)
        return pipeline().configuration(camera_id)

    @app.put("/api/cameras/{camera_id}/zones")
    def save_zones(camera_id: str, config: ZoneConfig):
        camera_exists(camera_id)
        pipeline().set_config(camera_id, config)
        return config

    def filters(camera_id, type, review_status, since, until):
        if since and since.tzinfo is None:
            since = since.replace(tzinfo=UTC)
        if until and until.tzinfo is None:
            until = until.replace(tzinfo=UTC)
        if since and until and since > until:
            raise HTTPException(400, "Start date must precede end date.")
        return {
            "camera_id": camera_id,
            "type": type,
            "review_status": review_status,
            "since": since.astimezone(UTC).isoformat().replace("+00:00", "Z") if since else None,
            "until": until.astimezone(UTC).isoformat().replace("+00:00", "Z") if until else None,
        }

    @app.get("/api/events")
    def events(
        camera_id: str | None = None,
        type: ObservationType | None = None,
        domain: Literal["people", "legacy"] | None = None,
        review_status: Literal["unreviewed", "acknowledged", "false_alarm"] | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
    ):
        return store().events(
            limit=limit,
            offset=offset,
            domain=domain,
            **filters(camera_id, type, review_status, since, until),
        )

    @app.get("/api/events/export")
    def export(
        format: Literal["csv", "json"] = "json",
        camera_id: str | None = None,
        type: str | None = None,
        domain: Literal["people", "legacy"] | None = None,
        review_status: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ):
        result = store().events(
            limit=10000, domain=domain, **filters(camera_id, type, review_status, since, until)
        )
        if result["total"] > 10000:
            raise HTTPException(400, "Narrow the date range to export at most 10,000 events.")
        rows = result["items"]
        if format == "json":
            return Response(
                json.dumps(rows, indent=2),
                media_type="application/json",
                headers={
                    "Content-Disposition": 'attachment; filename="flowpulse-observations.json"'
                },
            )
        output = io.StringIO()
        columns = [
            "id",
            "camera_id",
            "type",
            "state",
            "review_status",
            "started_at",
            "ended_at",
            "source_mode",
            "zone_id",
            "track_id",
            "explanation",
        ]
        writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    k: "'" + v if isinstance(v, str) and v.startswith(("=", "+", "-", "@")) else v
                    for k, v in row.items()
                }
            )
        return Response(
            output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="flowpulse-observations.csv"'},
        )

    @app.get("/api/events/{event_id}")
    def event(event_id: UUID):
        value = store().event(str(event_id))
        if not value:
            raise HTTPException(404, "Observation not found.")
        return value

    @app.patch("/api/events/{event_id}/review")
    def review(event_id: UUID, update: ReviewUpdate):
        value = store().review(str(event_id), update.review_status)
        if not value:
            raise HTTPException(404, "Observation not found.")
        pipeline().notify("event_updated", value)
        return value

    @app.get("/api/events/{event_id}/evidence")
    def evidence(event_id: UUID):
        event(event_id)
        path = pipeline().evidence.get(str(event_id))
        if not path:
            raise HTTPException(404, "Evidence disabled, unavailable or expired.")
        try:
            return Response(path.read_bytes(), media_type="image/jpeg")
        except OSError as exc:
            raise HTTPException(404, "Evidence expired or became unavailable.") from exc

    @app.get("/api/metrics/series")
    def series(window: int = Query(300, ge=10, le=3600)):
        cutoff = datetime.now(UTC).timestamp() - window
        with pipeline().lock:
            items = list(pipeline().series)
        return [
            item
            for item in items
            if datetime.fromisoformat(item["timestamp"].replace("Z", "+00:00")).timestamp()
            >= cutoff
        ]

    def frame_data(overlays: bool) -> bytes:
        p = pipeline()
        with p.lock:
            frame = p.annotated if overlays else p.raw
            if (
                frame is None
                or p.error is not None
                or not p.last_processed
                or p.state == "OFFLINE"
                or (p.state != "PAUSED" and time_since(p.last_processed) > p.frame_max_age())
                or "frozen_input" in p.quality_flags
            ):
                raise HTTPException(503, "No current processed frame. Check source diagnostics.")
            return frame

    @app.get("/api/stream/frame.jpg")
    def frame(overlays: bool = True, camera_id: str | None = None, frame_id: str | None = None):
        p = pipeline()
        with p.lock:
            if camera_id is not None and camera_id != p.camera_id:
                raise HTTPException(409, "Source changed; wait for the selected camera frame.")
            if frame_id is not None and frame_id != p.frame_id:
                raise HTTPException(409, "Frame changed; wait for its current status update.")
            return Response(
                frame_data(overlays),
                media_type="image/jpeg",
                headers={
                    "X-RoadPulse-Camera-Id": p.camera_id,
                    "X-RoadPulse-Frame-Id": p.frame_id or "",
                    "X-RoadPulse-Source-Image-Sha256": p.source_image_sha256 or "",
                },
            )

    @app.get("/api/stream/local-preview.mjpg")
    async def local_preview_stream(request: Request, camera_id: str):
        """Smooth, latest-only local-camera display; inference stays independent.

        Same-origin, opt-in camera session only. No recording, disk storage,
        snapshots of other devices, or long frame queues. The connection ends
        on stop/source switch and a stale capture is never replayed as live.
        """
        p = pipeline()
        with p.lock:
            if camera_id != p.camera_id or not camera_id.startswith("local-camera-"):
                raise HTTPException(409, "Selected local camera is no longer active.")
            if p.state in {"OFFLINE", "PAUSED", "STOPPING"}:
                raise HTTPException(409, "Local camera is not streaming.")
            generation = p.capture_generation

        async def latest_frames():
            last_sequence = -1
            while not await request.is_disconnected():
                with p.lock:
                    if (
                        p.capture_generation != generation
                        or p.camera_id != camera_id
                        or p.state in {"OFFLINE", "PAUSED", "STOPPING"}
                    ):
                        return
                    sequence = p.preview_sequence
                    data = p.preview_jpeg
                    captured = p.preview_capture_time
                    healthy = p.error is None and "frozen_input" not in p.quality_flags
                if (
                    data is not None
                    and healthy
                    and sequence != last_sequence
                    and 0 <= time_since(captured) <= 2.0
                ):
                    last_sequence = sequence
                    yield (
                        b"--frame\r\nContent-Type: image/jpeg\r\n"
                        + b"Cache-Control: no-store\r\nContent-Length: "
                        + str(len(data)).encode("ascii")
                        + b"\r\n\r\n"
                        + data
                        + b"\r\n"
                    )
                await asyncio.sleep(0.06)

        return StreamingResponse(
            latest_frames(),
            media_type="multipart/x-mixed-replace; boundary=frame",
            headers={
                "Cache-Control": "no-store, no-cache, max-age=0, no-transform",
                "X-Content-Type-Options": "nosniff",
                "X-Accel-Buffering": "no",
            },
        )

    @app.get("/api/stream/annotated.mjpg")
    async def stream(request: Request):
        if pipeline().mode == "SNAPSHOT":
            raise HTTPException(
                409,
                "Current snapshots have no continuous video stream. Use the JPEG frame endpoint.",
            )

        async def generate():
            while not await request.is_disconnected():
                try:
                    data = frame_data(True)
                except HTTPException:
                    await asyncio.sleep(0.5)
                    continue
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + data + b"\r\n"
                await asyncio.sleep(1 / pipeline().config.rules.target_fps)

        return StreamingResponse(generate(), media_type="multipart/x-mixed-replace; boundary=frame")

    @app.websocket("/ws/live")
    async def live(socket: WebSocket):
        if socket.headers.get("origin") not in settings.origins:
            await socket.close(code=1008)
            return
        await socket.accept()
        last = pipeline().sequence
        try:
            while True:
                await socket.send_json(
                    {"version": 1, "type": "status", "data": pipeline().status()}
                )
                with pipeline().lock:
                    notifications = [n for n in pipeline().notifications if n["sequence"] > last]
                    metric = pipeline().series[-1] if pipeline().series else None
                if metric:
                    await socket.send_json({"version": 1, "type": "metrics", "data": metric})
                for notification in notifications:
                    await socket.send_json(notification)
                    last = notification["sequence"]
                # Local-only status refresh is faster than the inference rate,
                # so sampled overlay positions are not held for a whole second.
                # This does NOT increase YOLO work or camera capture frequency.
                await asyncio.sleep(0.35)
        except (WebSocketDisconnect, RuntimeError, OSError):
            pass

    return app


def time_since(timestamp: float) -> float:
    import time

    return time.monotonic() - timestamp


app = create_app()
