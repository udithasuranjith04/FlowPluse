import copy
import hashlib
import queue
import threading
import time
from collections import deque
from pathlib import Path

import cv2
import numpy as np

from app.auto_insights import AutomaticInsights
from app.capabilities import capabilities
from app.config import Settings
from app.digitraffic import (
    DigitrafficService,
    DigitrafficSnapshot,
    ProviderError,
)
from app.digitraffic import (
    age as source_age,
)
from app.evidence import EvidenceStore
from app.flow import FlowEngine
from app.local_camera import LocalCameraSource, resolve_device
from app.person_detail import PersonDetailScanner
from app.person_evidence import PersonEvidenceGate
from app.quality import Continuity, ViewStability
from app.rules import RuleEngine, utc_now
from app.schemas import ZoneConfig, demo_zones
from app.sources import SnapshotSource, SourceError, SyntheticSource, VideoSource, validate_source
from app.storage import Store
from app.tracking import Tracker
from app.vision import SyntheticDetector, YoloDetector
from app.visual_overlay import build_visual_overlays


class Pipeline:
    def __init__(self, settings: Settings, store: Store):
        self.settings, self.store = settings, store
        self.lock = threading.RLock()
        self.control = threading.RLock()
        self.stop_event = threading.Event()
        self.threads: list[threading.Thread] = []
        self.frames: queue.Queue = queue.Queue(maxsize=1)
        self.notifications: deque = deque(maxlen=200)
        self.sequence = 0
        self.series: deque = deque(maxlen=3600)
        self.logs: deque = deque(maxlen=80)
        self.capture_times: deque = deque(maxlen=120)
        self.process_times: deque = deque(maxlen=120)
        self.latencies: deque = deque(maxlen=120)
        self.evidence = EvidenceStore(
            settings.evidence_dir, settings.save_evidence, settings.evidence_ttl_hours
        )
        self.digitraffic = DigitrafficService(settings.digitraffic_user)
        self.local_device: dict | None = None
        self.provider_camera: dict | None = None
        self.source_timestamp: str | None = None
        self.timestamp_kind = "local receipt time"
        self.next_refresh: str | None = None
        self.frame_id: str | None = None
        self.source_image_sha256: str | None = None
        self.visible_vehicles: int | None = None
        self.visible_people: int | None = None
        # Bounded, in-memory frame-count trend. No raw images or identities are retained.
        self.people_count_history: deque[dict] = deque(maxlen=90)
        self.auto_insights = AutomaticInsights()
        self.detection_boxes: list[dict] = []
        self.track_details: list[dict] = []
        # Recent *visual* hints are not counted as current detections.
        self.overlay_tracks: list[dict] = []
        self.weak_person_confirmations = 0
        self.detail_scan_mode = "inactive"
        self.detail_scan_additional_candidates = 0
        self.detail_scan_duplicate_proposals = 0
        self.detail_scan_closeup_candidates = 0
        self.detector_input_size: int | None = None
        self.resolution: list[int] | None = None
        self.capture_generation = 0
        self.continuous_frames_verified = False
        self.previous_live_digest: bytes | None = None
        self.live_frame_count = 0
        self.device_released = True
        self.preview_only = False
        self.control_revision = time.monotonic_ns() // 1000
        self.detector_cache: YoloDetector | None = None
        self.camera_id = "demo"
        self.config = self.configuration("demo")
        self.engine: RuleEngine | FlowEngine = RuleEngine(
            "demo", self.config, "REPLAY", SyntheticDetector.name
        )
        self.raw: bytes | None = None
        self.annotated: bytes | None = None
        # Latest-only, memory-only camera preview. Independent of 2 FPS AI inference.
        self.preview_jpeg: bytes | None = None
        self.preview_sequence = 0
        self.preview_capture_time = 0.0
        self.preview_times: deque = deque(maxlen=45)
        self.last_capture = 0.0
        self.last_processed = 0.0
        self.last_processed_capture = 0.0
        self.processing_delay_ms: float | None = None
        self.last_inference_ms: float | None = None
        self.started = time.monotonic()
        self.state = "OFFLINE"
        self.mode = "OFFLINE"
        self.input_type = "not_opened"
        self.model = "Not loaded"
        self.actual_device = settings.device
        self.device_note: str | None = None
        self.error: str | None = None
        self.dropped = self.reconnects = self.active_tracks = self.session_events = 0
        self.quality_flags: list[str] = []
        # Remains set until this monitoring session ends. Do not save a shift
        # that may contain measurements from multiple camera viewpoints.
        self.view_shift_detected = False
        self.frame_timestamp: str | None = None
        self.store.resolve_interrupted(utc_now())

    def _engine(
        self, camera_id: str, config: ZoneConfig, mode: str, model: str
    ) -> RuleEngine | FlowEngine:
        if camera_id != "demo" and self.settings.detection_target == "person":
            return FlowEngine(camera_id, config, mode, model)
        return RuleEngine(camera_id, config, mode, model)

    def cameras(self) -> list[dict]:
        items = self.settings.cameras() + (
            self.digitraffic.cameras() if self.settings.digitraffic_enabled else []
        )
        if self.provider_camera and self.camera_id not in {c["id"] for c in items}:
            items.append(self.digitraffic.public(self.provider_camera))
        if self.local_device:
            for item in items:
                if item["id"] == f"local-camera-{self.settings.local_camera_index}":
                    item["name"] = self.local_device["name"]
        return items

    def configuration(self, camera_id: str) -> ZoneConfig:
        default = demo_zones() if camera_id == "demo" else ZoneConfig()
        default.rules.target_fps = self.settings.target_fps
        return self.store.get_config(camera_id, default)

    def log(self, message: str) -> None:
        with self.lock:
            self.logs.appendleft({"at": utc_now(), "message": message})

    def notify(self, kind: str, data: dict) -> None:
        with self.lock:
            self.sequence += 1
            self.notifications.append(
                {"version": 1, "sequence": self.sequence, "type": kind, "data": copy.deepcopy(data)}
            )

    def save_changes(self, changes: list[dict], tracks: list | None = None) -> None:
        for event in changes:
            old = self.store.event(event["id"])
            if old:
                event["evidence_url"] = old["evidence_url"]
            else:
                event["evidence_url"] = self.evidence.save(event["id"], tracks or [])
                self.session_events += 1
            saved = self.store.put_event(event)
            kind = (
                "event_resolved"
                if event["state"] == "resolved"
                else "event_updated"
                if old
                else "event_created"
            )
            self.notify(kind, saved)

    def stop(self) -> None:
        with self.control:
            if (
                self.camera_id.startswith("local-camera-")
                and not self.preview_only
                and not self.view_shift_detected
                and self.state not in {"OFFLINE", "PAUSED"}
            ):
                summary = self.auto_insights.snapshot().get("session_summary", {})
                if self.store.archive_shift(self.camera_id, self.config.staff_only_region, summary):
                    self.log("Anonymous shift aggregate saved with owner opt-in.")
            self._stop()

    def pause(self) -> None:
        """Intentional pause releases capture too; only its last frame is retained."""
        with self.control:
            if self.state in {"OFFLINE", "PAUSED"}:
                raise SourceError("Start this source before pausing it.")
            self._stop(paused=True)

    def resume(self) -> None:
        with self.control:
            if self.state != "PAUSED":
                raise SourceError("Resume is available only for an intentionally paused source.")
            self.activate(self.camera_id, preview=self.preview_only)

    def _stop(self, paused: bool = False) -> None:
        self.stop_event.set()
        with self.lock:
            self.control_revision = max(self.control_revision + 1, time.monotonic_ns() // 1000)
            self.capture_generation += 1
            self.state = "STOPPING"
        for thread in self.threads:
            thread.join(timeout=15)
        if any(thread.is_alive() for thread in self.threads):
            # Never start a second worker while the previous detector is still running.
            raise SourceError("Worker is still stopping. Retry after inference finishes.")
        if not self.device_released:
            raise SourceError(
                "Capture did not confirm release. Stop the backend before reopening the camera."
            )
        self.threads = []
        with self.lock:
            self.save_changes(self.engine.reset("operator_paused" if paused else "session_ended"))
            self.state = "PAUSED" if paused else "OFFLINE"
            self.device_released = True
            self.continuous_frames_verified = False
            self.previous_live_digest = None
            self.live_frame_count = 0
            self.capture_times.clear()
            self.process_times.clear()
            self.track_details = []
            self.overlay_tracks = []
            self.weak_person_confirmations = 0
            self.detail_scan_mode = "inactive"
            self.detail_scan_additional_candidates = 0
            self.detail_scan_duplicate_proposals = 0
            self.detail_scan_closeup_candidates = 0
            self.detector_input_size = None
            self.visible_vehicles = None
            self.visible_people = None
            self.people_count_history.clear()
            self.auto_insights.reset()
            self.detection_boxes = []
            self.preview_jpeg = None
            self.preview_capture_time = 0.0
            self.preview_times.clear()
            self.error = None
            if not paused:
                self.raw = self.annotated = None
                self.frame_id = None
                self.source_image_sha256 = None
                self.frame_timestamp = None
                self.last_capture = self.last_processed = self.last_processed_capture = 0
            self.active_tracks = 0
            self.quality_flags = []
            self.view_shift_detected = False

    def activate_local(
        self,
        index: int,
        preview: bool = False,
        device_id: str | None = None,
    ) -> None:
        """Explicit API consent is scoped to an owned device and this process."""
        with self.control:
            selected = resolve_device(device_id) if device_id else None
            # Release before mutating the active device identity.
            self.stop()
            self.local_device = selected
            if selected:
                index = selected["index"]
            self.settings.local_camera_index = index
            self.settings.local_camera_authorized = True
            self.activate(f"local-camera-{index}", preview=preview)

    def activate(self, camera_id: str, preview: bool = False) -> None:
        with self.control:
            if camera_id not in {c["id"] for c in self.cameras()}:
                raise SourceError("Unknown camera.")
            self._stop()
            with self.lock:
                self.camera_id = camera_id
                self.control_revision = max(self.control_revision + 1, time.monotonic_ns() // 1000)
                self.frame_id = self.source_image_sha256 = None
                self.visible_vehicles = None
                self.visible_people = None
                self.people_count_history.clear()
                self.auto_insights.reset()
                self.detection_boxes = []
                self.track_details = []
                self.overlay_tracks = []
                self.weak_person_confirmations = 0
                self.detail_scan_mode = "inactive"
                self.detail_scan_additional_candidates = 0
                self.detail_scan_duplicate_proposals = 0
                self.detail_scan_closeup_candidates = 0
                self.detector_input_size = None
                self.preview_jpeg = None
                self.preview_capture_time = 0.0
                self.resolution = None
                self.previous_live_digest = None
                self.live_frame_count = 0
                self.continuous_frames_verified = False
                self.preview_only = preview
                self.source_timestamp = None
                self.provider_camera = None
                self.input_type = "not_opened"
                self.timestamp_kind = "unknown"
                self.frame_timestamp = self.next_refresh = None
                self.last_capture = self.last_processed = self.last_processed_capture = 0
                self.last_inference_ms = self.processing_delay_ms = None
                self.capture_times.clear()
                self.process_times.clear()
                self.latencies.clear()
                self.series.clear()
                self.model = "Not loaded"
            try:
                provider_camera = (
                    self.digitraffic.camera(camera_id)
                    if camera_id.startswith("digitraffic-")
                    else None
                )
                if provider_camera and not self.settings.digitraffic_enabled:
                    raise SourceError("Digitraffic is disabled in local settings.")
                if provider_camera and not Path(self.settings.model_path).is_file():
                    raise SourceError("YOLO weights missing. Run make model.")
                local = camera_id == f"local-camera-{self.settings.local_camera_index}"
                if local:
                    if not self.settings.local_camera_authorized:
                        raise SourceError(
                            "Local camera needs explicit ownership/analysis/display consent."
                        )
                    if not Path(self.settings.model_path).is_file():
                        raise SourceError("YOLO weights missing. Run make model.")
                if camera_id != "demo" and provider_camera is None and not local:
                    issues = self.settings.source_issues()
                    if issues:
                        raise SourceError(" ".join(issues))
                    validate_source(self.settings)
            except (SourceError, ProviderError) as exc:
                with self.lock:
                    self.error = str(exc)
                raise
            with self.lock:
                self.stop_event = threading.Event()
                self.camera_id = camera_id
                self.provider_camera = provider_camera
                self.source_timestamp = None
                self.timestamp_kind = "unknown" if provider_camera else "local receipt time"
                self.next_refresh = None
                self.frame_id = None
                self.source_image_sha256 = None
                self.visible_vehicles = None
                self.visible_people = None
                self.detection_boxes = []
                self.overlay_tracks = []
                self.weak_person_confirmations = 0
                self.detail_scan_mode = "inactive"
                self.detail_scan_additional_candidates = 0
                self.detail_scan_duplicate_proposals = 0
                self.detail_scan_closeup_candidates = 0
                self.detector_input_size = None
                self.mode = (
                    "REPLAY"
                    if camera_id == "demo"
                    else "LIVE"
                    if local
                    else "SNAPSHOT"
                    if provider_camera
                    else self.settings.camera_mode.upper()
                )
                self.config = self.configuration(camera_id)
                self.frames = queue.Queue(maxsize=1)
                self.capture_times.clear()
                self.process_times.clear()
                self.latencies.clear()
                self.series.clear()
                self.last_capture = self.last_processed = self.last_processed_capture = 0
                self.processing_delay_ms = None
                self.last_inference_ms = None
                self.dropped = self.reconnects = self.session_events = 0
                self.frame_timestamp = None
                self.quality_flags = []
                self.view_shift_detected = False
                self.error = None
                self.state = "CONNECTING"
                self.input_type = "not_opened"
                self.model = "Loading"
                self.actual_device = "cpu" if camera_id == "demo" else self.settings.device
                self.device_note = None
                self.started = time.monotonic()
                self.engine = self._engine(camera_id, self.config, self.mode, "Loading")
            self.log(f"Starting {self.mode} source.")
            self.threads = [
                threading.Thread(target=self._capture, daemon=True),
                threading.Thread(target=self._process, daemon=True),
            ]
            for thread in self.threads:
                thread.start()

    def set_config(self, camera_id: str, config: ZoneConfig) -> None:
        self.store.save_config(camera_id, config)
        with self.lock:
            if camera_id == self.camera_id:
                self.save_changes(self.engine.reset("configuration_changed"))
                self.config = config
                self.engine = self._engine(camera_id, config, self.mode, self.model)
                # Geometry changes invalidate shift comparisons across old/new view areas.
                self.auto_insights.reset()
                self.people_count_history.clear()
        self.log("Monitoring configuration saved; rule baselines reset.")

    def _capture(self) -> None:
        attempt = 0
        generation = 0
        last_provider_digest: bytes | None = None
        next_preview_at = 0.0
        while not self.stop_event.is_set():
            source: (
                SyntheticSource
                | VideoSource
                | SnapshotSource
                | DigitrafficSnapshot
                | LocalCameraSource
                | None
            ) = None
            try:
                with self.lock:
                    self.device_released = False
                if self.camera_id == "demo":
                    source = SyntheticSource()
                elif self.camera_id.startswith("local-camera-"):
                    source = (
                        LocalCameraSource(
                            self.settings.local_camera_index,
                            device_id=self.local_device["device_id"],
                        )
                        if self.local_device
                        else LocalCameraSource(self.settings.local_camera_index)
                    )
                elif self.provider_camera:
                    source = DigitrafficSnapshot(self.digitraffic, self.provider_camera)
                else:
                    target = validate_source(self.settings)
                    source = (
                        SnapshotSource(target, self.settings)
                        if self.mode == "SNAPSHOT"
                        else VideoSource(
                            target, replay=self.mode == "REPLAY", settings=self.settings
                        )
                    )
                with self.lock:
                    self.state = "CONNECTING"
                    self.input_type = source.input_type
                    self.device_released = False
                    self.capture_generation += 1
                    generation = self.capture_generation
                    self.previous_live_digest = None
                    self.live_frame_count = 0
                    self.continuous_frames_verified = False
                epoch = getattr(source, "epoch", 0)
                while not self.stop_event.is_set():
                    previous_drops = getattr(source, "dropped_frames", 0)
                    frame = source.read()
                    with self.lock:
                        self.dropped += max(
                            0, getattr(source, "dropped_frames", 0) - previous_drops
                        )
                    if frame is None and isinstance(source, DigitrafficSnapshot):
                        if self.stop_event.wait(2):
                            break
                        continue
                    if frame is None:
                        raise SourceError("Source stopped delivering frames. Reconnecting.")
                    if self.stop_event.is_set():
                        break
                    if self.mode == "LIVE":
                        live_digest = hashlib.sha256(frame.tobytes()).digest()
                        with self.lock:
                            self.live_frame_count += 1
                            if (
                                self.previous_live_digest is not None
                                and live_digest != self.previous_live_digest
                            ):
                                self.continuous_frames_verified = True
                            self.previous_live_digest = live_digest
                    if isinstance(source, DigitrafficSnapshot):
                        frame_digest = hashlib.sha256(frame.tobytes()).digest()
                        if frame_digest == last_provider_digest:
                            if self.stop_event.wait(2):
                                break
                            continue
                        last_provider_digest = frame_digest
                    now = getattr(source, "captured_at", 0) or time.monotonic()
                    next_epoch = getattr(source, "epoch", 0)
                    with self.lock:
                        if next_epoch != epoch:
                            self.save_changes(self.engine.reset("replay_loop"))
                        epoch = next_epoch
                        self.state = self.mode
                        self.last_capture = now
                        self.capture_times.append(now)
                    packet = (
                        frame,
                        now,
                        utc_now(),
                        generation * 1_000_000 + epoch,
                        source.source_timestamp
                        if isinstance(source, DigitrafficSnapshot)
                        else None,
                        source.timestamp_kind
                        if isinstance(source, DigitrafficSnapshot)
                        else "local receipt time",
                        source.next_refresh if isinstance(source, DigitrafficSnapshot) else None,
                        source.digest.hex()
                        if isinstance(source, DigitrafficSnapshot) and source.digest
                        else None,
                    )
                    if self.frames.full():
                        try:
                            self.frames.get_nowait()
                            self.dropped += 1
                        except queue.Empty:
                            pass
                    self.frames.put_nowait(packet)
                    # Publish camera frames separately from inference. This makes the
                    # owner preview responsive even when YOLO samples only ~2 FPS.
                    # Only the most recent compressed JPEG stays in memory; do not
                    # record, queue, or serve a camera that has since been switched.
                    if isinstance(source, LocalCameraSource):
                        tick = time.monotonic()
                        if tick >= next_preview_at:
                            next_preview_at = tick + (1 / 15)  # cap preview rendering at 15 FPS
                            self.publish_camera_preview(frame, now, generation)
                    attempt = 0
                    if isinstance(source, (SyntheticSource, SnapshotSource, DigitrafficSnapshot)):
                        if self.stop_event.wait(
                            2
                            if isinstance(source, DigitrafficSnapshot)
                            else self.settings.snapshot_interval_seconds
                            if self.mode == "SNAPSHOT"
                            else 1 / self.config.rules.target_fps
                        ):
                            break
            except (SourceError, ProviderError, cv2.error, OSError, ValueError) as exc:
                if self.stop_event.is_set():
                    break
                with self.lock:
                    self.capture_generation += (
                        1  # Invalidate in-flight inference from this session.
                    )
                    self.state = "RECONNECTING"
                    self.error = (
                        str(exc)
                        if isinstance(exc, (SourceError, ProviderError))
                        else "Source unavailable. Check format, access and URL expiry."
                    )
                    self.raw = self.annotated = None
                    self.active_tracks = 0
                    self.track_details = []
                    self.visible_vehicles = None
                    self.visible_people = None
                    self.detection_boxes = []
                    self.reconnects += 1
                    self.save_changes(self.engine.reset("stream_interrupted"))
                self.log("Source interrupted; retrying with bounded backoff.")
                if self.stop_event.wait(min(30, 2 ** min(attempt, 5))):
                    break
                attempt += 1
            finally:
                try:
                    if source is not None:
                        source.close()
                    with self.lock:
                        self.device_released = True
                except Exception:
                    with self.lock:
                        self.device_released = False
                        self.error = (
                            "Capture could not close. "
                            "Stop the backend before reopening this camera."
                        )
                    self.stop_event.set()

    def publish_camera_preview(self, frame: np.ndarray, captured: float, generation: int) -> None:
        """Bounded, latest-frame preview for a consented local camera only.

        Encodes outside the state lock, so rendering cannot stall inference.
        An in-flight encode is discarded after camera switch, stop or pause.
        """
        if not self.camera_id.startswith("local-camera-") or self.stop_event.is_set():
            return
        try:
            ok, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 76])
        except cv2.error:
            return  # Display may lag but the AI worker and source stay healthy.
        if not ok:
            return
        with self.lock:
            if (
                self.stop_event.is_set()
                or generation != self.capture_generation
                or not self.camera_id.startswith("local-camera-")
            ):
                return
            self.preview_jpeg = jpeg.tobytes()
            self.preview_capture_time = captured
            self.preview_sequence += 1
            self.preview_times.append(time.monotonic())

    def _process(self) -> None:
        try:
            if self.camera_id == "demo":
                detector: SyntheticDetector | YoloDetector = SyntheticDetector()
            else:
                if self.detector_cache is None:
                    self.detector_cache = YoloDetector(
                        self.settings.model_path,
                        self.settings.device,
                        self.settings.detection_target,
                    )
                detector = self.detector_cache
        except Exception:  # Sanitize dependency/model errors at the worker boundary.
            with self.lock:
                self.error = "Detector unavailable. Install vision dependencies and run make model."
                self.model = "Unavailable"
                self.state = "OFFLINE"
            self.stop_event.set()
            self.log("Inference could not start. See model setup in README.")
            return
        tracker = Tracker()
        evidence = PersonEvidenceGate()
        detail_scanner = PersonDetailScanner()
        with self.lock:
            self.model = detector.name
            self.engine.model = detector.name
        continuity = Continuity()
        stability = ViewStability()
        previous_thumb = None
        while not self.stop_event.is_set():
            iteration = time.monotonic()
            try:
                (
                    frame,
                    captured,
                    timestamp,
                    epoch,
                    source_time,
                    timestamp_kind,
                    next_refresh,
                    source_hash,
                ) = self.frames.get(timeout=0.5)
            except queue.Empty:
                if self.last_capture and time.monotonic() - self.last_capture > 3:
                    with self.lock:
                        self.save_changes(self.engine.reset("stale_input"))
                        self.active_tracks = 0
                        self.overlay_tracks = []
                    tracker.reset()
                    evidence.reset()
                    detail_scanner.reset()
                continue
            try:
                thumb = cv2.resize(frame, (64, 36))
                digest = hashlib.sha256(thumb.tobytes()).digest()
                change = (
                    float(np.abs(thumb.astype(float) - previous_thumb).mean()) / 255
                    if previous_thumb is not None
                    else 0.0
                )
                flags = continuity.update(
                    digest, captured, change, epoch, self.config.rules.target_fps
                )
                if self.camera_id.startswith("local-camera-"):
                    if stability.update(frame, captured):
                        flags.append("camera_view_moving")
                if flags:
                    if "camera_view_moving" in flags or "camera_movement" in flags:
                        with self.lock:
                            if not self.view_shift_detected:
                                self.log(
                                    "Camera viewpoint changed; shift history will not be saved "
                                    "for this session."
                                )
                            self.view_shift_detected = True
                    tracker.reset()
                    evidence.reset()
                    detail_scanner.reset()
                    with self.lock:
                        self.people_count_history.clear()
                        self.auto_insights.reset()
                        self.overlay_tracks = []
                        self.save_changes(self.engine.reset("input_discontinuity"))
                previous_thumb = thumb.astype(float)
                start = time.perf_counter()
                person_target = (
                    self.camera_id != "demo" and self.settings.detection_target == "person"
                )
                threshold = self.config.rules.min_confidence
                # Weak candidate boxes are never counted on the first sighting;
                # accept one only after a second independent model observation.
                candidates = detector.detect(
                    frame,
                    PersonEvidenceGate.candidate_floor(threshold) if person_target else threshold,
                )
                if person_target and isinstance(detector, YoloDetector):
                    candidates = detail_scanner.augment(
                        detector, frame, candidates, PersonEvidenceGate.candidate_floor(threshold)
                    )
                detections = (
                    evidence.filter(candidates, captured, threshold)
                    if person_target
                    else candidates
                )
                inference_ms = (time.perf_counter() - start) * 1000
                finished = time.monotonic()
                too_slow = finished - captured > max(2.5, 2 / self.config.rules.target_fps)
                if too_slow:
                    flags.append("slow_processing")
                if self.mode == "SNAPSHOT":
                    flags.append("snapshot_no_tracking")
                quality = not flags and not self.preview_only
                if self.mode == "LIVE" and not self.continuous_frames_verified:
                    quality = False
                tracks = tracker.update(detections, captured) if self.mode != "SNAPSHOT" else []
                with self.lock:
                    if epoch // 1_000_000 != self.capture_generation:
                        continue
                    self.save_changes(self.engine.step(tracks, captured, quality), tracks)
                    self.quality_flags = flags
                    self.active_tracks = len(tracks)
                    self.auto_insights.step(
                        detections,
                        tracks,
                        captured,
                        healthy=(
                            self.mode == "LIVE"
                            and self.continuous_frames_verified
                            and not flags
                            and self.settings.detection_target == "person"
                        ),
                        monitoring=not self.preview_only,
                        staff_only_region=self.config.staff_only_region,
                    )
                    annotated = self._draw(frame.copy(), tracks, detections)
                    if isinstance(detector, YoloDetector):
                        self.actual_device = detector.device
                        self.device_note = detector.device_note
                    ok_raw, raw = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 82])
                    ok_ann, ann = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 85])
                    if not ok_raw or not ok_ann:
                        raise RuntimeError("Processed JPEG encoding failed")
                    self.raw, self.annotated = raw.tobytes(), ann.tobytes()
                    self.last_processed = finished
                    self.last_processed_capture = captured
                    self.processing_delay_ms = round((finished - captured) * 1000, 2)
                    self.frame_timestamp = timestamp
                    self.frame_id = hashlib.sha256(frame.tobytes()).hexdigest()
                    self.source_image_sha256 = source_hash
                    self.source_timestamp = source_time
                    self.timestamp_kind = timestamp_kind
                    self.next_refresh = next_refresh
                    person_target = (
                        self.camera_id != "demo" and self.settings.detection_target == "person"
                    )
                    self.visible_people = len(detections) if person_target else None
                    self.visible_vehicles = None if person_target else len(detections)
                    if (
                        person_target
                        and self.mode == "LIVE"
                        and self.continuous_frames_verified
                        and not flags
                    ):
                        self.people_count_history.append(
                            {"at": timestamp, "people": self.visible_people}
                        )
                    self.detection_boxes = [
                        {"box": list(d.box), "label": d.label, "confidence": d.confidence}
                        for d in detections
                    ]
                    self.track_details = [
                        {
                            "id": track.id,
                            "box": list(track.detection.box),
                            "label": track.detection.label,
                            "confidence": track.detection.confidence,
                            "image_plane_motion_per_second": track.motion,
                        }
                        for track in tracks
                    ]
                    # Visualization is deliberately isolated from counters and
                    # observations; an unverified last-seen hint is never live.
                    self.overlay_tracks = build_visual_overlays(
                        tracks,
                        tracker.tracks,
                        captured,
                        allow_held=(
                            person_target
                            and self.mode == "LIVE"
                            and self.continuous_frames_verified
                            and not flags
                        ),
                    )
                    self.weak_person_confirmations = evidence.weak_admitted if person_target else 0
                    self.detail_scan_mode = detail_scanner.mode if person_target else "inactive"
                    self.detail_scan_additional_candidates = (
                        detail_scanner.added_candidates if person_target else 0
                    )
                    self.detail_scan_duplicate_proposals = (
                        detail_scanner.suppressed_duplicates if person_target else 0
                    )
                    self.detail_scan_closeup_candidates = (
                        detail_scanner.closeup_candidates if person_target else 0
                    )
                    self.detector_input_size = (
                        getattr(detector, "person_image_size", None) if person_target else None
                    )
                    self.resolution = [frame.shape[1], frame.shape[0]]
                    self.last_inference_ms = round(inference_ms, 3)
                    self.latencies.append(inference_ms)
                    self.process_times.append(finished)
                    # EOF may be reached while the last queued frame is finishing.
                    # Do not change a completed test clip back to LIVE/STALE.
                    if self.state not in {"RECONNECTING", "OFFLINE", "FINISHED"}:
                        self.error = None
                        self.state = self.mode
                    self.series.append(
                        {
                            "timestamp": timestamp,
                            "camera_id": self.camera_id,
                            "occupancy": max(
                                (z["occupancy"] for z in self.engine.debug), default=0
                            ),
                            "count": len(tracks),
                            "processed_fps": self._fps(self.process_times),
                            "inference_ms": inference_ms,
                        }
                    )
                self.evidence.purge()
            except Exception:  # Never expose decoder/model exceptions containing source secrets.
                with self.lock:
                    self.error = "Frame processing failed; temporal observations are suspended."
                    self.active_tracks = 0
                    self.track_details = []
                    self.overlay_tracks = []
                    self.weak_person_confirmations = 0
                    self.detail_scan_mode = "inactive"
                    self.detail_scan_additional_candidates = 0
                    self.detail_scan_duplicate_proposals = 0
                    self.detail_scan_closeup_candidates = 0
                    self.visible_vehicles = None
                    self.visible_people = None
                    self.quality_flags = ["processing_error"]
                    self.save_changes(self.engine.reset("processing_error"))
                tracker.reset()
                self.log("Frame processing error; skipping this frame.")
            self.stop_event.wait(
                max(0, 1 / self.config.rules.target_fps - (time.monotonic() - iteration))
            )

    def _draw(self, image: np.ndarray, tracks: list, detections: list | None = None) -> np.ndarray:
        h, w = image.shape[:2]
        for line in self.config.lines if isinstance(self.engine, FlowEngine) else []:
            (ax, ay), (bx, by) = line.points
            a, b = (int(ax * w), int(ay * h)), (int(bx * w), int(by * h))
            cv2.line(image, a, b, (60, 220, 180), 2, cv2.LINE_AA)
            cv2.circle(image, a, 5, (60, 220, 180), -1)
            cv2.putText(
                image,
                f"{line.name[:22]}: - to + = IN",
                (max(0, a[0]), max(18, a[1] - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.42,
                (60, 220, 180),
                1,
                cv2.LINE_AA,
            )
        for zone in self.config.zones:
            points = np.array([(x * w, y * h) for x, y in zone.points], dtype=np.int32)
            color = (180, 190, 65) if zone.kind == "monitoring_lane" else (100, 100, 180)
            cv2.polylines(image, [points], True, color, 1, cv2.LINE_AA)
            cv2.putText(
                image,
                zone.name[:32],
                (int(points[0, 0]), int(points[0, 1])),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                color,
                1,
                cv2.LINE_AA,
            )
        active_ids = {e["track_id"] for e in self.engine.active.values()}
        boxes = [(t.detection, t.id) for t in tracks]
        if self.mode == "SNAPSHOT":
            boxes = [(d, "snapshot") for d in (detections or [])]
        for detection, track_id in boxes:
            x1, y1, x2, y2 = detection.box
            color = (75, 185, 250) if track_id in active_ids else (220, 220, 80)
            cv2.rectangle(image, (int(x1 * w), int(y1 * h)), (int(x2 * w), int(y2 * h)), color, 2)
            caption = f"{detection.label} {detection.confidence:.0%}"
            if track_id != "snapshot":
                caption += f" #{track_id.split(':')[-1]}"
            cv2.putText(
                image,
                caption,
                (int(x1 * w), max(18, int(y1 * h) - 7)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.42,
                color,
                1,
                cv2.LINE_AA,
            )
        return image

    @staticmethod
    def _fps(times: deque) -> float:
        now = time.monotonic()
        recent = [t for t in times if now - t <= 20]
        return (
            round((len(recent) - 1) / (recent[-1] - recent[0]), 2)
            if len(recent) > 1 and recent[-1] > recent[0]
            else 0.0
        )

    def frame_max_age(self) -> float:
        return (
            1800
            if self.provider_camera
            else max(3, self.settings.snapshot_interval_seconds * 2)
            if self.mode == "SNAPSHOT"
            else 3
        )

    def status(self) -> dict:
        with self.lock:
            now = time.monotonic()
            age = now - self.last_capture if self.last_capture else None
            processed_age = now - self.last_processed if self.last_processed else None
            displayed_age = (
                now - self.last_processed_capture if self.last_processed_capture else None
            )
            state = self.state
            if state == "OFFLINE" and not self.device_released:
                state = "STOPPING"
            if state == "LIVE" and not self.continuous_frames_verified:
                state = "CONNECTING"
            provider_age = source_age(self.source_timestamp)
            authorized = (
                (
                    self.camera_id.startswith("local-camera-")
                    and self.settings.local_camera_authorized
                )
                or self.camera_id == "demo"
                or self.provider_camera is not None
                or (
                    self.settings.camera_analysis_authorized
                    and self.settings.camera_redisplay_authorized
                )
            )
            if (
                state not in {"OFFLINE", "PAUSED"}
                and self.provider_camera
                and self.last_processed
                and (provider_age is None or provider_age > 1800)
            ):
                state = "STALE"
            if (
                state in {"LIVE", "REPLAY", "SNAPSHOT"}
                and age is not None
                and age > (self.frame_max_age())
            ):
                state = "STALE"
            if state in {"LIVE", "REPLAY", "SNAPSHOT"} and "frozen_input" in self.quality_flags:
                state = "STALE"
            return {
                "camera_id": self.camera_id,
                "view_shift_detected": self.view_shift_detected,
                "control_revision": self.control_revision,
                "mode": self.mode,
                "state": state,
                "model": self.model,
                "input_type": self.input_type,
                "source_kind": "CURRENT CAMERA SNAPSHOT"
                if self.provider_camera
                else "LOCAL LIVE CAMERA"
                if self.camera_id.startswith("local-camera-")
                else "SYNTHETIC DEMO"
                if self.camera_id == "demo"
                else "LIVE VIDEO"
                if self.mode == "LIVE"
                else self.mode,
                "device": self.actual_device,
                "device_note": self.device_note,
                "ai_state": "active"
                if processed_age is not None
                and processed_age < (self.frame_max_age())
                and not self.error
                and state not in {"OFFLINE", "PAUSED", "STALE", "RECONNECTING", "FINISHED"}
                else "loading"
                if self.model == "Loading" and state not in {"PAUSED", "OFFLINE", "FINISHED"}
                else "paused",
                "source_timestamp": self.source_timestamp,
                "source_age_seconds": round(provider_age, 1) if provider_age is not None else None,
                "timestamp_kind": self.timestamp_kind,
                "next_refresh_estimate": self.next_refresh,
                "visible_vehicles": self.visible_vehicles,
                "visible_people": self.visible_people,
                "staff_only_region": self.config.staff_only_region,
                "automatic_insights": self.auto_insights.snapshot()
                if self.settings.detection_target == "person" and self.camera_id != "demo"
                else None,
                "people_count_history": list(self.people_count_history)
                if self.settings.detection_target == "person" and self.camera_id != "demo"
                else [],
                "flow": {
                    "entries": self.engine.entries,
                    "exits": self.engine.exits,
                    "zone_counts": self.engine.zone_counts.copy(),
                    "lines": [line.model_dump() for line in self.config.lines],
                }
                if isinstance(self.engine, FlowEngine)
                else None,
                "detection_target": (
                    "vehicle" if self.camera_id == "demo" else self.settings.detection_target
                ),
                "detections": self.detection_boxes.copy(),
                "tracks": copy.deepcopy(self.track_details),
                "overlay_tracks": copy.deepcopy(self.overlay_tracks),
                "weak_person_confirmations": self.weak_person_confirmations,
                "detail_scan_mode": self.detail_scan_mode,
                "detail_scan_additional_candidates": self.detail_scan_additional_candidates,
                "detail_scan_duplicate_proposals": self.detail_scan_duplicate_proposals,
                "detail_scan_closeup_candidates": self.detail_scan_closeup_candidates,
                "detector_input_size": self.detector_input_size,
                "resolution": self.resolution,
                "device_released": self.device_released,
                "preview_only": self.preview_only,
                "continuous_frames_verified": self.continuous_frames_verified,
                "consecutive_frames_received": self.live_frame_count,
                "monitoring_zones_configured": any(
                    z.kind == "monitoring_lane" for z in self.config.zones
                )
                or (isinstance(self.engine, FlowEngine) and bool(self.config.lines)),
                "capabilities": {
                    **capabilities("snapshot" if self.mode == "SNAPSHOT" else "video", authorized),
                    "capture_timestamp_available": self.timestamp_kind == "provider measuredTime"
                    and self.source_timestamp is not None,
                },
                "temporal_rules_enabled": self.mode != "SNAPSHOT"
                and authorized
                and state in {"LIVE", "REPLAY"}
                and not self.quality_flags
                and not self.preview_only
                and (
                    any(z.kind == "monitoring_lane" for z in self.config.zones)
                    or (isinstance(self.engine, FlowEngine) and bool(self.config.lines))
                ),
                "attribution": self.provider_camera.get("attribution")
                if self.provider_camera
                else None,
                "frame_timestamp": self.frame_timestamp,
                "frame_id": self.frame_id,
                "source_image_sha256": self.source_image_sha256,
                "frame_age_seconds": round(age, 2) if age is not None else None,
                "processed_frame_age_seconds": round(displayed_age, 2)
                if displayed_age is not None
                else None,
                "processing_delay_ms": self.processing_delay_ms,
                "ingest_fps": self._fps(self.capture_times),
                "preview_fps": self._fps(self.preview_times),
                "processed_fps": self._fps(self.process_times),
                "inference_ms": self.last_inference_ms,
                "latency_p50_ms": round(float(np.percentile(list(self.latencies), 50)), 2)
                if self.latencies
                else None,
                "latency_p95_ms": round(float(np.percentile(list(self.latencies), 95)), 2)
                if self.latencies
                else None,
                "dropped_frames": self.dropped,
                "reconnect_count": self.reconnects,
                "queue_depth": self.frames.qsize(),
                "active_tracks": self.active_tracks,
                "session_events": self.session_events,
                "uptime_seconds": round(now - self.started),
                "last_error": self.error,
                "quality_flags": self.quality_flags.copy(),
                "rule_debug": copy.deepcopy(self.engine.debug),
                "evidence_enabled": self.settings.save_evidence,
                "evidence_error": self.evidence.last_error,
                "logs": list(self.logs),
            }
