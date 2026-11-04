import { useEffect, useRef, useState } from "react";
import {
  Activity, ArrowDownToLine, ArrowRight, Camera, Check, ChevronLeft,
  ChevronRight, CircleHelp, HeartPulse,
  Maximize2, Pause, Play, RefreshCw, ScanLine, ShieldCheck,
  Square, Users, Wifi, WifiOff, X, Coffee, Clock3, Settings2, Bell, Lightbulb, ChevronDown,
} from "lucide-react";
import { api, time, title } from "./api";
import { CameraSetup } from "./CameraSetup";
import { CafeShift } from "./CafeShift";
import { GuestAreaSetup } from "./GuestAreaSetup";
import { SceneDiscoveryPanel } from "./SceneDiscoveryPanel";
import { deriveServiceSignals, ServiceAlertsPage, ServiceSignalList, useDesktopAlerts } from "./ServiceAlerts";
import { StartupScreen } from "./StartupScreen";
import { useLive } from "./useLive";
import { emptyOverlayMemory, presentOverlays, reconcileOverlaySample } from "./overlayPresentation";
import type { OverlayMemory } from "./overlayPresentation";
import ZoneEditor from "./ZoneEditor";
import type { Camera as CameraType, EventPage, Observation, Review, Status } from "./types";

type Page = "Overview" | "Shift" | "Alerts" | "Camera & Zones" | "Diagnostics" | "About";
const pages = [
  { id: "Overview", label: "Live café", icon: Coffee },
  { id: "Shift", label: "Shift summary", icon: Clock3 },
  { id: "Alerts", label: "Service alerts", icon: Bell },
  { id: "Camera & Zones", label: "Camera setup", icon: Camera },
  { id: "Diagnostics", label: "System health", icon: Activity },
  { id: "About", label: "About FlowPulse", icon: CircleHelp },
] as const;
function isPeopleSource(status: Status | null) {
  return Boolean(status && status.camera_id.startsWith("local-camera-") && status.detection_target === "person");
}
/** Hide a point-in-time count when its underlying inference is not trustworthy.
 * Historical shift aggregates are intentionally left available and labeled separately.
 */
export function currentCountTrusted(status: Status | null): boolean {
  return Boolean(status && isPeopleSource(status) && status.state === "LIVE" &&
    status.ai_state === "active" && !status.preview_only && !status.last_error &&
    !status.view_shift_detected &&
    status.continuous_frames_verified === true &&
    (status.quality_flags?.length ?? 0) === 0 &&
    typeof status.processed_frame_age_seconds === "number" &&
    Number.isFinite(status.processed_frame_age_seconds) &&
    status.processed_frame_age_seconds >= 0 && status.processed_frame_age_seconds <= 3);
}
function hasLiveFrame(status: Status | null) {
  return Boolean(status?.frame_id && status.ai_state === "active" &&
    (["LIVE", "REPLAY", "SNAPSHOT"].includes(status.state) || status.preview_only || status.state === "PAUSED"));
}

/** Retained as a small source-state contract for the existing status tests. */
export function ModeBadge({ mode, synthetic = false, currentSnapshot = false, localCamera = false, continuousVerified = false }: {
  mode: string; synthetic?: boolean; currentSnapshot?: boolean; localCamera?: boolean; continuousVerified?: boolean;
}) {
  const label = currentSnapshot && mode === "SNAPSHOT" ? "CURRENT CAMERA SNAPSHOT" :
    mode === "REPLAY" && synthetic ? "REPLAY DEMO" :
    mode === "LIVE" ? (!continuousVerified ? "VERIFYING VIDEO" : localCamera ? "MY LIVE CAMERA" : "CONTINUOUS VIDEO") : mode;
  return <span className={`studio-state state-${mode.toLowerCase()}`}><span className="pulse-dot"/>{label}</span>;
}

export function LivePreview({ status, camera }: { status: Status | null; camera?: CameraType }) {
  const frame = useRef<HTMLDivElement>(null);
  const [overlays, setOverlays] = useState(true);
  const [retry, setRetry] = useState(0);
  const [failed, setFailed] = useState(false);
  const [renderClock, setRenderClock] = useState(() => Date.now());
  const [overlayMemory, setOverlayMemory] = useState<OverlayMemory>(emptyOverlayMemory);
  const fresh = hasLiveFrame(status) && isPeopleSource(status);
  const smooth = fresh && status?.camera_id.startsWith("local-camera-") && status.state === "LIVE";
  // MJPEG video and AI samples have separate clocks. Keep last confirmed
  // coordinates steady, then switch to a bounded unverified amber hint.
  useEffect(() => {
    if (!smooth || !overlays) return;
    const ticker = window.setInterval(() => setRenderClock(Date.now()), 100);
    return () => window.clearInterval(ticker);
  }, [smooth, overlays]);
  const legacy = Boolean(status && (status.camera_id === "demo" || status.detection_target !== "person"));
  const width = status?.resolution?.[0] || 1280;
  const height = status?.resolution?.[1] || 720;
  const sourceKey = `${status?.camera_id ?? ""}:${status?.control_revision ?? 0}`;
  const sampleKey = status?.frame_timestamp
    ? `${status.frame_timestamp}:${status.frame_id ?? ""}` : status?.frame_id ?? "";
  const sampleTime = status?.frame_timestamp ? Date.parse(status.frame_timestamp) : NaN;
  const captureTime = Number.isFinite(sampleTime)
    ? sampleTime : Date.now() - (status?.processed_frame_age_seconds ?? Infinity) * 1000;
  // Repeated WebSocket updates of the *same* inference are not fresh evidence.
  // The visual layer is separate from all backend counts and shift measurements.
  useEffect(() => {
    if (!smooth || !overlays || !status || status.last_error ||
        !status.frame_id || status.ai_state !== "active" ||
        (status.processed_frame_age_seconds ?? Infinity) > 3 ||
        (status.quality_flags ?? []).some((flag) =>
          ["camera_view_moving", "camera_movement", "frozen_input", "source_boundary", "frame_gap"].includes(flag))) {
      setOverlayMemory(emptyOverlayMemory());
      return;
    }
    setOverlayMemory((old) => reconcileOverlaySample(old, {
      source: sourceKey, sample: sampleKey, capturedAtMs: captureTime,
      tracks: status.overlay_tracks ?? status.tracks ?? [],
    }, Date.now()));
  }, [smooth, overlays, status, sourceKey, sampleKey, captureTime]);
  const boxes = smooth && overlays && status?.ai_state === "active" && !status.last_error &&
    (status.processed_frame_age_seconds ?? Infinity) <= 3
    ? presentOverlays(overlayMemory.source === sourceKey ? overlayMemory : emptyOverlayMemory(),
      renderClock, status?.processed_fps, status?.processing_delay_ms ?? 0)
    : [];
  return <section className="studio-card camera-stage" aria-label="Live camera preview">
    <div className="stage-heading"><div><span className="section-kicker">LIVE / VISION</span><h2>Camera workspace</h2></div>
      <div className="stage-tools"><button className={`studio-tool ${overlays ? "selected" : ""}`} aria-pressed={overlays} onClick={() => setOverlays(!overlays)}> <ScanLine size={15}/> Overlays</button>
        <button className="studio-icon-btn" aria-label="Expand camera view" onClick={() => void frame.current?.requestFullscreen?.()}><Maximize2 size={17}/></button>
      </div>
    </div>
    <div className="stage-viewport" ref={frame}>
      {smooth ? <>
        <img key={`${status!.camera_id}:${status!.control_revision ?? 0}:${retry}`}
          src={`/api/stream/local-preview.mjpg?camera_id=${encodeURIComponent(status!.camera_id)}&revision=${status!.control_revision ?? 0}&attempt=${retry}`}
          alt={`Live person-detection camera ${camera?.name || status!.camera_id}`}
          onLoad={() => setFailed(false)} onError={() => setFailed(true)} />
        {boxes.length > 0 && <svg className="stage-ai-boxes" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="xMidYMid meet" aria-label="Latest sampled AI detection boxes">
          {boxes.map((track) => {
            const [x1, y1, x2, y2] = track.box;
            const x = x1 * width;
            const y = y1 * height;
            return <g key={track.visualId} opacity={track.state === "confirmed" ? 0.95 : 0.58}>
              <rect x={x} y={y} width={(x2 - x1) * width} height={(y2 - y1) * height}
                fill="none" stroke={track.state === "last-seen" ? "#f6c57c" : "#70e6d1"}
                strokeDasharray={track.state === "last-seen" ? "10 7" : undefined}
                strokeWidth={Math.max(2, width / 500)} />
              <text x={x + 4} y={Math.max(18, y - 6)} fill={track.state === "last-seen" ? "#f6d6a4" : "#c0ffed"}
                fontSize={Math.max(14, width / 80)} fontWeight="600">
                {track.state === "last-seen" ? "last seen · not verified" : "person · sampled"}
              </text>
            </g>;
          })}
        </svg>}
      </> : fresh ? <img key={`${status?.camera_id}:${status?.frame_id}:${overlays}:${retry}`}
        src={`/api/stream/frame.jpg?overlays=${overlays}&camera_id=${encodeURIComponent(status!.camera_id)}&frame_id=${encodeURIComponent(status!.frame_id || "")}&attempt=${retry}`}
        alt={`Live person-detection camera ${camera?.name || status!.camera_id}`} onLoad={() => setFailed(false)} onError={() => setFailed(true)} />
      : <div className="stage-placeholder"><div className="stage-graphic"><ScanLine size={66} strokeWidth={1}/><span/></div>
          <span className="stage-placeholder-kicker">{legacy ? "LEGACY SOURCE INACTIVE FOR PEOPLE FLOW" : "READY WHEN YOU ARE"}</span>
          <h3>{legacy ? "Switch to a people-flow camera" : status?.state === "CONNECTING" ? "Opening the camera" : "Your live view will appear here"}</h3>
          <p>{legacy ? "Old traffic demos and snapshots are not presented as people-flow measurements. Stop that source, then preview your own camera." : "Choose your own Mac or iPhone camera and preview it before starting anonymous monitoring."}</p>
        </div>}
      {status?.state === "CONNECTING" && <div className="stage-connecting" role="status"><span className="spinning"><Activity size={15}/></span> Initializing local camera…</div>}
      {fresh && status?.processed_frame_age_seconds != null && status.processed_frame_age_seconds > 3 && <div className="stage-frame-error" role="alert">AI sample is stale ({status.processed_frame_age_seconds.toFixed(1)}s). Check the camera connection before using the analytics.</div>}
      {failed && fresh && <div className="stage-frame-error" role="alert">Camera preview connection interrupted. <button onClick={() => { setFailed(false); setRetry((v) => v + 1); }}>Reconnect preview</button></div>}
      {fresh && <div className="stage-overlay-chip"><span className="pulse-dot"/> {status?.preview_only ? "PREVIEW ONLY" : "LOCAL LIVE"} · {smooth ? "SMOOTH VIDEO" : "PERSON DETECTION"}</div>}
      {status?.preview_only && fresh && <div className="stage-preview-note">Preview mode · analytics events disabled until monitoring starts</div>}
    </div>
    <div className="stage-footer"><span><span className="pulse-dot"/> {fresh ? (status?.continuous_frames_verified ? "Changing frames verified" : "Checking frame continuity") : "Waiting for authorized camera"}</span>
      <span>{smooth ? `Video ${status?.preview_fps?.toFixed(1) ?? "—"} FPS · AI ${status?.processed_fps?.toFixed(1) ?? "—"} FPS${status?.detector_input_size ? ` · Detail ${status.detector_input_size}px` : ""}${status?.detail_scan_mode === "scanning" ? " · Close-up scans on" : status?.detail_scan_mode === "performance_limited" ? " · Close-up scans cooling" : ""} · Solid: detected · Dashed: last seen (not counted)` : fresh ? `Frame age ${status?.processed_frame_age_seconds?.toFixed(1) ?? "—"}s` : "Local inference · no cloud"}</span></div>
  </section>;
}

function RecentActivity({ status, onShift }: { status: Status; onShift: () => void }) {
  const filtered = status.staff_only_region && status.staff_only_region !== "none" && (status.automatic_insights?.guest_area_recent?.length ?? 0) > 0;
  const points = (filtered ? status.automatic_insights!.guest_area_recent!.map((people) => ({ people })) : status.people_count_history ?? []).filter((p) => Number.isFinite(p.people) && p.people >= 0);
  const peak = Math.max(1, ...points.map((p) => p.people));
  const coordinates = points.map((p, i) => `${12 + (i / Math.max(1, points.length - 1)) * 576},${120 - p.people / peak * 92}`).join(" ");
  return <section className="owner-panel cafe-recent-activity"><div className="owner-panel-heading"><div><span className="owner-eyebrow">RECENT CAMERA ACTIVITY</span><h2>How the floor is changing</h2><p>{filtered ? "People in your selected guest-facing area" : "Everyone visible in the camera"} · last {points.length} processed frames.</p></div><button className="owner-link-button" onClick={onShift}>Shift details <ArrowRight size={15}/></button></div>
    {points.length >= 3 ? <svg viewBox="0 0 600 145" preserveAspectRatio="none" role="img" aria-label={`Recent activity across ${points.length} frames`}><path d="M12 28 H588 M12 74 H588 M12 120 H588" fill="none" stroke="currentColor" strokeDasharray="4 7" opacity=".18"/><polyline fill="none" stroke="#78e1c8" strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round" points={coordinates}/></svg> : <div className="owner-chart-empty">Collecting live frames…</div>}
    <p className="owner-fineprint">Counts are estimates from the camera view. This chart is not customer arrivals, order volume, or sales.</p>
  </section>;
}

function Overview({ status, camera, events, toZones, toEvents, toShift }: {
  status: Status | null; camera?: CameraType; events: Observation[]; toZones: () => void; toEvents: () => void; toShift: () => void;
}) {
  const isLive = isPeopleSource(status) && status?.ai_state === "active";
  const auto = isLive ? status?.automatic_insights : null;
  const filtered = isLive && status?.staff_only_region && status.staff_only_region !== "none" && auto?.guest_area_visible != null;
  const trustedNow = currentCountTrusted(status);
  const guests = !trustedNow ? null : filtered ? auto?.guest_area_visible : status?.visible_people;
  const trend = auto?.visible_trend;
  const shiftSustainedPeak = auto?.session_summary?.supported_peak_visible;
  const peakNeedsReview = auto?.session_summary?.peak_possible_outlier === true;
  const paceLabel = !isLive ? "Not live" : !trustedNow ? "Checking signal" : ({ warming_up: "Learning", rising: "Rising", steady: "Steady", falling: "Calmer" }[trend || "warming_up"]);
  const liveSignals = deriveServiceSignals(status, events);
  const attention = liveSignals.find((signal) => signal.level === "attention");
  const moved = Boolean(status?.view_shift_detected || status?.quality_flags?.includes("camera_view_moving"));
  const stale = (status?.processed_frame_age_seconds ?? 0) > 3 || (status?.quality_flags?.length ?? 0) > 0;
  return <div className="owner-page">
    <header className="owner-page-heading owner-overview-heading"><div><span className="owner-eyebrow">YOUR CAFÉ, RIGHT NOW</span><h1>Know your floor at a glance.</h1><p>Live people counts, automatic alerts and useful shift patterns—all measured locally.</p></div><span className={`owner-context-chip ${isLive ? "is-live" : ""}`}><span className="pulse-dot"/>{isLive ? status?.preview_only ? "Camera preview" : "Monitoring live" : "Awaiting camera"}</span></header>
    <div className="owner-summary-grid owner-overview-metrics">
      <div className="owner-summary-card owner-summary-emphasis"><Users size={20}/><span>{filtered ? "People visible now · guest area" : "People visible now · full camera"}</span><strong>{guests ?? "—"}</strong><small>{!trustedNow ? "Waiting for a verified, recent AI sample" : filtered ? `Full camera now: ${status?.visible_people ?? "—"} · not verified customers` : "Includes staff · not a customer count"}</small></div>
      <div className="owner-summary-card"><Activity size={20}/><span>Current activity</span><strong>{paceLabel}</strong><small>A simple camera-view indicator, not an occupancy limit</small></div>
      <div className="owner-summary-card"><TrendingUpIcon/><span>Highest sustained count this shift</span><strong>{shiftSustainedPeak ?? "Learning"}</strong><small>{peakNeedsReview ? "A larger one-frame count needs review" : "Median across five nearby AI samples · estimate"}</small></div>
    </div>
    {isLive && moved && <div className="studio-warning" role="status">The camera viewpoint changed during this session. Scene evidence was restarted, and this shift will not be saved as a historical comparison. For meaningful insights, restart with a fixed camera.</div>}
    {isLive && <div className="guest-area-callout"><ShieldCheck size={17}/><span>{filtered ? "Staff-only side excluded from the guest-area estimate. This does not identify customers." : "AI learns repeated activity locations automatically. The camera cannot verify who is staff or a customer."}</span><button onClick={toZones}>{filtered ? "Change area" : "View AI scene map"} <ArrowRight size={14}/></button></div>}
    <div className="owner-live-grid"><div className="owner-live-primary"><LivePreview status={status} camera={camera}/>
      {status?.preview_only && isLive && <div className="owner-preview-cta"><div><strong>Your preview is working</strong><p>To collect shift data, finish the camera setup and select Start monitoring.</p></div><button className="owner-action-button" onClick={toZones}>Continue setup <ArrowRight size={15}/></button></div>}
      {isLive && <RecentActivity status={status!} onShift={toShift}/>}
      {isLive && <SceneDiscoveryPanel status={status} compact/>}
      {!isLive && <section className="owner-panel owner-offline-start"><div><span className="owner-eyebrow">YOUR CAMERA IS NOT RUNNING</span><h2>Ready to see your café?</h2><p>Camera setup helps you connect a permitted stationary camera.</p></div><button className="owner-action-button" onClick={toZones}>Go to Camera setup <ArrowRight size={16}/></button></section>}
    </div><aside className="owner-live-aside">
      <section className={`owner-panel owner-help-card ${stale ? "needs-attention" : ""}`}><span className="owner-eyebrow"><Lightbulb size={15}/> NEXT BEST STEP</span>
        <h2>{!isLive ? "Start with a clear camera view" : moved ? "Keep the camera stationary" : stale ? "Check the camera signal" : attention?.title ?? "No sudden change detected"}</h2>
        <p>{!isLive ? "A fixed view of the permitted café floor or counter helps produce useful measurements." : moved ? "The camera viewpoint has changed. Temporal counts and learned areas must restart once the camera is still." : stale ? "Input quality is uncertain; avoid acting on these numbers until the feed is healthy." : attention?.suggestion ?? "No sustained change needs attention right now. Keep checking the floor as usual."}</p>
        <button className="owner-action-button" onClick={isLive ? toShift : toZones}>{isLive ? "See shift activity" : "Set up camera"}<ArrowRight size={16}/></button>
      </section>
      <section className="owner-panel owner-alert-preview"><div className="owner-panel-heading"><div><span className="owner-eyebrow">AUTOMATIC ALERTS</span><h2>What needs attention?</h2></div></div>
        <ServiceSignalList compact signals={liveSignals.filter((signal) => signal.level === "attention")}/>
        <button className="owner-link-button" onClick={toEvents}>View service alerts <ArrowRight size={16}/></button>
      </section>
      {liveSignals.some((signal) => signal.level === "info" && signal.id.startsWith("scene-")) && <section className="owner-panel owner-insight-quiet"><span className="owner-eyebrow">DISCOVERED PATTERN · NO ACTION NEEDED</span><p>FlowPulse has noticed recurring activity areas. See the scene map below for details. Seating is not a service alert.</p></section>}
      <section className="owner-panel owner-privacy-card"><ShieldCheck size={22}/><div><strong>Private by design</strong><p>On-device video processing. No face recognition or customer profiles.</p></div></section>
    </aside></div>
    <p className="owner-fineprint">Café insights are estimates from visible frames, not sales, exact wait times, customer visits or a certified headcount. Keep the camera fixed and use permitted scenes with participant notice.</p>
  </div>;
}

/** Clear icon stand-in with the existing icon pack, kept separate from financial claims. */
function TrendingUpIcon() { return <Activity size={20} aria-hidden="true"/>; }

function ObservationDialog({ event, close, reviewed }: { event: Observation; close: () => void; reviewed: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  const [current, setCurrent] = useState(event);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { ref.current?.showModal(); return () => ref.current?.close(); }, []);
  async function review(review_status: Review) {
    setBusy(true); setError("");
    try { const next = await api<Observation>(`/api/events/${current.id}/review`, { method: "PATCH", body: JSON.stringify({ review_status }) }); setCurrent(next); reviewed(); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not save review"); }
    finally { setBusy(false); }
  }
  return <dialog ref={ref} className="studio-dialog" onCancel={close} aria-label="Observation details">
    <div className="dialog-top"><span className="section-kicker">OBSERVATION / EVIDENCE</span><button aria-label="Close observation details" className="studio-icon-btn" onClick={close}><X size={20}/></button></div>
    <h2>{title(current.type)}</h2><p>{current.explanation}</p>
    <div className="dialog-values"><div><span>Zone</span><b>{current.zone_name}</b></div><div><span>State</span><b>{current.state}</b></div>
      <div><span>Review</span><b>{current.review_status.replaceAll("_", " ")}</b></div><div><span>Started</span><b>{new Date(current.started_at).toLocaleString()}</b></div>
      <div><span>Anonymous track</span><b>{current.track_id || "Zone level"}</b></div><div><span>Model</span><b>{current.model_version}</b></div></div>
    <details><summary>Measured features and rules</summary><pre>{JSON.stringify({ features: current.features, rule_parameters: current.rule_parameters, quality_flags: current.quality_flags }, null, 2)}</pre></details>
    {error && <p role="alert" className="error-text">{error}</p>}
    <div className="dialog-buttons"><button disabled={busy} className="studio-button primary" onClick={() => void review("acknowledged")}><Check size={15}/> Acknowledge</button>
      <button disabled={busy} className="studio-button secondary" onClick={() => void review("false_alarm")}>Mark false alarm</button>
      <button disabled={busy} className="studio-button ghost" onClick={() => void review("unreviewed")}>Reset review</button></div>
  </dialog>;
}

function EventsPage({ cameraId, cameras, revision, onSelect }: { cameraId: string; cameras: CameraType[]; revision: number; onSelect: (e: Observation) => void }) {
  const [oldData, setOldData] = useState(false);
  const [filter, setFilter] = useState("");
  const [review, setReview] = useState("");
  const [source, setSource] = useState("");
  const [offset, setOffset] = useState(0);
  const [rows, setRows] = useState<EventPage | null>(null);
  const [error, setError] = useState("");
  const params = new URLSearchParams({ limit: "20", offset: String(offset) });
  if (!oldData) params.set("domain", "people");
  if (source) params.set("camera_id", source);
  if (filter) params.set("type", filter);
  if (review) params.set("review_status", review);
  const query = params.toString();
  useEffect(() => { let active = true; setError(""); api<EventPage>(`/api/events?${query}`)
    .then((value) => { if (active) setRows(value); }).catch((e) => { if (active) setError(e instanceof Error ? e.message : "Could not read events"); });
    return () => { active = false; }; }, [query, revision]);
  const page = rows?.items || [];
  return <div className="studio-page-stack"><div className="page-intro"><span className="section-kicker">CAFÉ / OBSERVATIONS</span><h1>Stay on top of service.</h1><p>Review possible waiting and crowding signals. No automated judgments about customers.</p></div>
    <section className="studio-card archive"><div className="archive-head"><div><h2>Service observations</h2><p>Locally saved signals. Mark anything incorrect so your reviews stay useful.</p></div><a className="studio-button secondary" href={`/api/events/export?format=csv&${query}`} download><ArrowDownToLine size={16}/> Export CSV</a></div>
      <div className="archive-filters"><label>Type<select value={filter} onChange={(e) => { setOffset(0); setFilter(e.target.value); }}><option value="">All service signals</option><option value="extended_dwell">Guest stayed in area</option><option value="possible_queue_buildup">Possible line forming</option></select></label>
      <label>Review<select value={review} onChange={(e) => { setOffset(0); setReview(e.target.value); }}><option value="">All reviews</option><option value="unreviewed">Unreviewed</option><option value="acknowledged">Acknowledged</option><option value="false_alarm">False alarm</option></select></label>
      <label>Camera<select value={source} onChange={(e) => { setOffset(0); setSource(e.target.value); }}><option value="">All cameras</option>{cameras.filter((c) => c.id !== "demo").map((c) => <option value={c.id} key={c.id}>{c.name}</option>)}{cameraId.startsWith("local-camera-") && !cameras.some((c) => c.id === cameraId) && <option value={cameraId}>{cameraId}</option>}</select></label>
      <details className="owner-archive-advanced"><summary>Archive options</summary><label className="legacy-switch"><input type="checkbox" checked={oldData} onChange={(e) => { setOffset(0); setOldData(e.target.checked); }}/> Include historical demo data (not café observations)</label></details></div>
      {error && <p className="error-text" role="alert">{error}</p>}
      {!rows ? <div className="archive-empty">Loading observations…</div> : page.length ? <div className="archive-list">{page.map((event) => <button key={event.id} className="observation-item" onClick={() => onSelect(event)}><span className="observation-icon"><Activity size={18}/></span><span className="observation-copy"><strong>{title(event.type)}</strong><small>{event.zone_name} · {event.camera_id === "demo" ? "Archived fixture" : event.camera_id} · {time(event.started_at)}</small></span><span className="observation-state">{event.review_status.replaceAll("_", " ")}</span><ChevronRight size={16}/></button>)}</div>
        : <div className="archive-empty"><ShieldCheck size={30}/><h3>All clear here</h3><p>No saved service alerts match these filters. Live guest counts and shift activity work without zones; saved dwell or queue signals need a suitable confirmed area.</p></div>}
      <div className="archive-bottom"><span>{rows?.total ?? 0} observations · page {Math.floor(offset / 20) + 1}</span><div><button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 20))}><ChevronLeft size={14}/> Previous</button><button disabled={offset + 20 >= (rows?.total ?? 0)} onClick={() => setOffset(offset + 20)}>Next <ChevronRight size={14}/></button></div></div>
      <p className="archive-footnote">An alert is a prompt to check the situation, not proof that someone is waiting. Previous demo data remains hidden by default.</p>
    </section></div>;
}

function Diagnostics({ status }: { status: Status | null }) {
  const healthy = Boolean(status?.ai_state === "active" && status.continuous_frames_verified && (status.processed_frame_age_seconds ?? Infinity) < 3 && !status.last_error);
  const rows: [string, string | number][] = status ? [
    ["Processing rate", `${status.processed_fps?.toFixed(2) ?? "—"} fps`], ["Camera capture rate", `${status.ingest_fps?.toFixed(2) ?? "—"} fps`],
    ["Inference median", status.latency_p50_ms == null ? "—" : `${status.latency_p50_ms} ms`],
    ["Inference p95", status.latency_p95_ms == null ? "—" : `${status.latency_p95_ms} ms`],
    ["Superseded / dropped frames", status.dropped_frames ?? "—"], ["Reconnects", status.reconnect_count ?? "—"],
    ["Device", status.device || "—"], ["Input", status.input_type || "Not active"],
    ["Camera capture", status.device_released == null ? "Not confirmed" : status.device_released ? "Released" : "Active"],
    ["Frame continuity", status.continuous_frames_verified ? "Verified" : "Unverified"],
    ["Detection target", status.detection_target || "—"], ["Resolution", status.resolution?.join(" × ") || "—"],
    ["Frame age", status.processed_frame_age_seconds == null ? "—" : `${status.processed_frame_age_seconds}s`],
    ["Model", status.model || "—"], ["Focused scan", status.detail_scan_mode || "Unavailable"],
    ["Current detected people", status.visible_people ?? "—"],
    ["Close-up candidate proposals", status.detail_scan_closeup_candidates ?? "—"],
    ["Overlap proposals suppressed", status.detail_scan_duplicate_proposals ?? "—"],
    ["Close-up candidates added", status.detail_scan_additional_candidates ?? "—"],
    ["Raw session maximum", status.automatic_insights?.session_summary?.peak_visible ?? "—"],
    ["Sustained high estimate", status.automatic_insights?.session_summary?.supported_peak_visible ?? "Learning"],
    ["One-frame peak warning", status.automatic_insights?.session_summary?.peak_possible_outlier ? "Possible isolated spike" : "None identified"],
    ["Queue depth", status.queue_depth ?? "—"],
    ["Monitoring", status.temporal_rules_enabled ? "Enabled" : "Disabled or previewing"],
    ["View consistency", status.view_shift_detected ? "View changed · restart to compare" : "No movement flagged"],
  ] : [];
  return <div className="owner-page"><header className="owner-page-heading"><div><span className="owner-eyebrow">SYSTEM HEALTH</span><h1>Is everything working?</h1><p>Simple camera checks first. Technical details are available if you need them.</p></div></header>
    <div className="owner-health-summary"><div className={`owner-health-indicator ${healthy ? "good" : "waiting"}`}><ShieldCheck size={32}/><div><strong>{healthy ? "Camera feed looks healthy" : status?.last_error ? "Camera needs attention" : "Waiting for a healthy live camera"}</strong><p>{healthy ? "Frames are changing and local analysis is active." : status?.last_error ?? "Open Camera setup, preview your camera and start monitoring."}</p></div></div>
      <div className="owner-health-mini"><span>Camera</span><strong>{status?.device_released === false ? "Connected" : "Not active"}</strong></div><div className="owner-health-mini"><span>Live frames</span><strong>{status?.continuous_frames_verified ? "Verified" : "Checking"}</strong></div><div className="owner-health-mini"><span>Analysis</span><strong>{status?.processed_fps == null ? "—" : `${status.processed_fps.toFixed(1)} fps`}</strong></div></div>
    {status?.quality_flags?.length ? <div className="quality-pills">{status.quality_flags.map((flag) => <span key={flag}>{flag.replaceAll("_", " ")}</span>)}</div> : <p className="owner-fineprint">No specific input-quality flags reported. A healthy connection does not guarantee accurate counts.</p>}
    <details className="owner-advanced-disclosure"><summary><span><Settings2 size={19}/><strong>Technical diagnostics</strong><small>Model, latency, tracking and frame-processing information</small></span><ChevronDown size={19}/></summary><div className="owner-advanced-content">
      <section className="studio-card"><div className="archive-head"><div><h2>Pipeline telemetry</h2><p>Measured by the current backend worker</p></div><span className="studio-state">{status?.ai_state || "OFFLINE"}</span></div><div className="system-grid">{rows.map(([name, value]) => <div key={name}><span>{name}</span><strong>{value}</strong></div>)}</div></section>
      <section className="studio-card"><div className="archive-head"><div><h2>Zone measurements</h2><p>Image-plane estimates, not physical density</p></div></div>
        {status?.rule_debug?.length ? <div className="rule-summary">{status.rule_debug.map((row) => <div key={row.zone_id}><strong>{row.name}</strong><span>{row.count} tracked</span><span>{row.queue_state.replaceAll("_", " ")}</span><span>Motion {row.motion?.toFixed(4) ?? "—"}</span></div>)}</div> : <div className="archive-empty">No optional zones are configured.</div>}
      </section>
      <section className="studio-card"><div className="archive-head"><div><h2>Session log</h2><p>Operational messages from the backend</p></div></div><div className="system-logs">{(status?.logs || []).map((row, i) => <div key={i}><time>{time(row.at)}</time><span>{row.message}</span></div>)}</div></section>
    </div></details>
  </div>;
}

function About() { return <div className="owner-page"><header className="owner-page-heading"><div><span className="owner-eyebrow">ABOUT FLOWPULSE</span><h1>Better service. Less guesswork.</h1><p>A private, local café assistant that turns an authorized camera view into simple measurements.</p></div></header>
  <div className="owner-about-grid"><section className="owner-panel owner-about-lead"><Coffee size={34}/><h2>Built for small café teams.</h2><p>See how many people are visible, understand changing activity during a shift, and receive automatic service alerts. You don't need to understand computer vision or sort through a review inbox.</p><div className="owner-about-steps"><div><b>01</b><strong>Connect</strong><span>Choose your own camera and approve a preview.</span></div><div><b>02</b><strong>Understand</strong><span>Read guest activity and simple local signals.</span></div><div><b>03</b><strong>Act</strong><span>Check service pressure with your team.</span></div></div></section>
  <section className="owner-panel owner-about-safety"><ShieldCheck size={30}/><h2>Privacy is part of the design.</h2><p>No face recognition, demographic inference, or persistent customer identities. Raw video isn't stored by default. Use permitted views and tell participants.</p><h3>What it cannot promise</h3><p>Not a certified count, exact arrival/departure time, verified queue length, or purchase analytics. Occlusion, movement, camera placement and temporary track changes can introduce errors.</p><h3>How it works</h3><p>YOLO11n person detection, short-lived anonymous tracks, FastAPI, SQLite and a React dashboard—all running locally.</p></section></div>
  <p className="owner-fineprint">FlowPulse Café Edition is a research/portfolio prototype. Test it with informed participants before real business decisions.</p>
</div>; }

export default function App() {
  const data = useLive();
  const [page, setPage] = useState<Page>("Overview");
  const [selected, setSelected] = useState<Observation | null>(null);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState("");
  const [revision, setRevision] = useState(0);
  const status = data.status;
  const camera = data.cameras.find((c) => c.id === status?.camera_id);
  const desktopAlerts = useDesktopAlerts(status, data.events.items);
  async function activateLocal(index: number, preview: boolean, deviceId?: string) {
    const id = `local-camera-${index}`;
    setBusy(true); setActionError(""); data.beginSourceChange(id);
    try {
      const next = await api<Status>(preview ? "/api/local-camera/preview" : "/api/local-camera/activate", {
        method: "POST", body: JSON.stringify({ device_index: index, device_id: deviceId,
          analysis_authorized: true, redisplay_authorized: true }),
      });
      data.sourceChanged(next); data.refresh(); return true;
    } catch (error) {
      const message = error instanceof Error ? error.message : "Camera activation failed";
      setActionError(message); data.sourceChangeFailed(message); return false;
    } finally { setBusy(false); }
  }
  async function control(action: "pause" | "resume" | "stop") {
    setBusy(true); setActionError("");
    try { const next = await api<Status>(`/api/system/${action}`, { method: "POST" }); data.controlChanged(next); data.refresh(); }
    catch (error) { setActionError(error instanceof Error ? error.message : `Could not ${action} camera`); data.refresh(); }
    finally { setBusy(false); }
  }
  const active = Boolean(status && !["OFFLINE", "FINISHED", "UNREACHABLE", "ERROR"].includes(status.state));
  const currentPeople = isPeopleSource(status);
  const legacy = Boolean(status?.camera_id === "demo" && active);
  if (data.initialLoading) return <StartupScreen />;
  return <div className="studio-shell">
    <aside className="studio-sidebar"><button className="studio-brand" onClick={() => setPage("Overview")} aria-label="FlowPulse AI overview"><span><HeartPulse size={26}/></span><strong>flowpulse<sup>AI</sup></strong></button>
      <span className="sidebar-label">CAFÉ OPERATIONS</span><nav aria-label="Main navigation">{pages.map(({ id, label, icon: Icon }) => <button key={id} aria-current={page === id ? "page" : undefined} className={page === id ? "selected" : ""} onClick={() => setPage(id)}><Icon size={18}/>{label}</button>)}</nav>
      <div className="sidebar-bottom"><div className="privacy-stamp"><ShieldCheck size={22}/><div><strong>Privacy first</strong><span>Runs on your Mac</span></div></div><span className="sidebar-version">CAFÉ EDITION · LOCAL FIRST</span></div>
    </aside>
    <div className="studio-content"><header className="studio-topbar"><span>YOUR CAFÉ <ChevronRight size={14}/> <strong>{pages.find((item) => item.id === page)?.label}</strong></span><div><span className={`connection-chip ${data.connected ? "connected" : ""}`}>{data.connected ? <Wifi size={14}/> : <WifiOff size={14}/>} {data.connected ? "Backend connected" : "Reconnecting"}</span><span className="topbar-divider"/><span className="topbar-local"> <ShieldCheck size={13}/> LOCAL</span></div></header>
      <main className="studio-main">
        {page !== "About" && <div className="studio-session"><div className="session-identity"><span className="session-symbol"><Camera size={19}/></span><div><small>CONNECTED CAMERA</small><strong>{currentPeople ? camera?.name || status?.camera_id : legacy ? "Legacy demonstration" : "Camera not connected"}</strong></div></div>
          <div className="session-commands"><ModeBadge mode={status && ["OFFLINE", "FINISHED", "PAUSED", "CONNECTING", "ERROR", "STALE"].includes(status.state) ? status.state : status?.mode || "OFFLINE"} localCamera={currentPeople} synthetic={legacy} continuousVerified={status?.continuous_frames_verified}/>
            {active && !legacy && status?.state !== "PAUSED" && <button className="studio-button secondary" disabled={busy} onClick={() => void control("pause")}><Pause size={16}/> Pause</button>}
            {status?.state === "PAUSED" && <button className="studio-button secondary" disabled={busy} onClick={() => void control("resume")}><Play size={16}/> Resume</button>}
            {(active) && <button className="studio-button danger" disabled={busy} onClick={() => void control("stop")}><Square size={14}/> Stop camera</button>}
            <button className="studio-icon-btn" aria-label="Refresh dashboard" onClick={data.refresh}><RefreshCw size={17}/></button></div></div>}
        {(data.error || actionError) && <div className="studio-error" role="alert"><WifiOff size={17}/><span>{actionError || data.error}</span><button onClick={() => { setActionError(""); data.refresh(); }}>Retry</button></div>}
        {legacy && <div className="studio-warning">The old vehicle fixture is still running. It isn't a people-flow source. Stop it, then preview a local camera. Existing legacy records are preserved in the archive.</div>}
        {status?.camera_id.startsWith("local-camera-") && status.detection_target === "vehicle" && <div className="studio-warning">The backend is still configured for vehicle detection. Set <code>ROADPULSE_DETECTION_TARGET=person</code> in your private .env and restart <code>make dev</code> before interpreting results.</div>}
        {page === "Overview" && <Overview status={status} camera={camera} events={data.events.items} toZones={() => setPage("Camera & Zones")} toEvents={() => setPage("Alerts")} toShift={() => setPage("Shift")}/>}
        {page === "Shift" && <CafeShift status={status} onCamera={() => setPage("Camera & Zones")}/>}
        {page === "Alerts" && <ServiceAlertsPage status={status} events={data.events.items} desktop={desktopAlerts} onCamera={() => setPage("Camera & Zones")}/>}
        {page === "Camera & Zones" && <div className="owner-page"><header className="owner-page-heading"><div><span className="owner-eyebrow">CAMERA & SETUP</span><h1>Simple start. Smart insights.</h1><p>Choose a permitted camera and start. FlowPulse automatically discovers repeated activity patterns, without asking you to draw zones.</p></div><span className="owner-context-chip"><ShieldCheck size={15}/> Private & local</span></header>
          <div className="owner-setup-grid"><div><span className="owner-eyebrow">GET STARTED · TWO MINUTES</span><h2 className="setup-start-heading">Make your camera a café assistant.</h2><CameraSetup status={status} busy={busy} activateLocal={activateLocal}/></div><aside className="owner-panel owner-setup-guide"><span className="owner-eyebrow">HOW IT WORKS</span><h2>Three simple steps</h2><div className="owner-steps"><div><b>1</b><p><strong>Choose a camera</strong><span>Keep a fixed view of the customer-facing area.</span></p></div><div><b>2</b><p><strong>Preview & approve</strong><span>Confirm you have permission and a clear, stable picture.</span></p></div><div><b>3</b><p><strong>Start monitoring</strong><span>Guest counts, session trends and visible-track timing run automatically.</span></p></div></div><div className="owner-trust-line"><ShieldCheck size={15}/> Your camera never starts by itself.</div></aside></div>
          {currentPeople && <SceneDiscoveryPanel status={status}/>}
          {currentPeople && camera && <details className="owner-advanced-disclosure scene-optional-region"><summary><span><Settings2 size={19}/><strong>Optional: exclude a known staff work area</strong><small>Only useful if the camera has a clearly separate staff-only side. Automatic scene discovery needs no selection.</small></span><ChevronDown size={19}/></summary><div className="owner-advanced-content"><GuestAreaSetup camera={camera} onSave={data.refresh}/></div></details>}
          <details className="owner-advanced-disclosure"><summary><span><Settings2 size={19}/><strong>Optional expert tools</strong><small>Only needed for calibrated entrance lines and specific waiting areas.</small></span><ChevronDown size={19}/></summary><div className="owner-advanced-content"><p><strong>Advanced image analysis already runs automatically.</strong> Entrance counting and location-specific queue detection cannot be assumed without a verified camera view. Open these tools only if you need those specific claims.</p>{currentPeople && camera ? <ZoneEditor key={camera.id} camera={camera} people onSave={data.refresh}/> : <div className="owner-empty-state">Connect a permitted local camera to configure optional physical zones.</div>}</div></details>
        </div>}
        {page === "Diagnostics" && <><Diagnostics status={status}/><details className="owner-advanced-disclosure cafe-archive-disclosure"><summary><span><Settings2 size={19}/><strong>Historical observation archive</strong><small>Optional developer review and CSV export. No need to label alerts for everyday café use.</small></span><ChevronDown size={19}/></summary><div className="owner-advanced-content"><EventsPage cameraId={status?.camera_id || ""} cameras={data.cameras} revision={revision} onSelect={setSelected}/></div></details></>}
        {page === "About" && <About/>}
        <footer className="studio-footer"><span><HeartPulse size={15}/> FlowPulse AI</span><span>Private by design · Clear estimates, not certified counts</span></footer>
      </main>
    </div>
    {selected && <ObservationDialog key={selected.id} event={selected} close={() => setSelected(null)} reviewed={() => { setRevision((v) => v + 1); data.refresh(); }}/>} </div>;
}
