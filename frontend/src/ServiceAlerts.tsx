import { useEffect, useMemo, useRef, useState } from "react";
import { Activity, ArrowRight, Bell, BellOff, CheckCircle2, CircleAlert, Eye, ShieldCheck } from "lucide-react";
import type { Observation, Status } from "./types";

export interface ServiceSignal {
  id: string;
  title: string;
  detail: string;
  suggestion: string;
  level: "attention" | "info";
}

/** Only camera-derived, actionable signals. No inferred customer identity or queue. */
export function deriveServiceSignals(status: Status | null, events: Observation[] = []): ServiceSignal[] {
  if (status?.camera_id?.startsWith("local-camera-") && ["STALE", "UNREACHABLE", "ERROR", "RECONNECTING"].includes(status.state)) {
    return [{ id: "camera-unhealthy", title: "Check your camera", detail: "The live feed or backend connection may be interrupted.", suggestion: "Check the camera connection before relying on the numbers.", level: "attention" }];
  }
  if (!status || status.ai_state !== "active" || status.detection_target !== "person" || !status.camera_id.startsWith("local-camera-") || status.state !== "LIVE") {
    return [{ id: "camera-offline", title: "Monitoring isn't active", detail: "The café isn't being measured right now.", suggestion: "Go to Camera setup to preview and start a permitted camera.", level: "info" }];
  }
  if (status.preview_only) {
    return [{ id: "camera-preview", title: "Camera preview is ready", detail: "Preview mode does not collect shift measurements or service alerts.", suggestion: "Start monitoring when the scene and permissions are confirmed.", level: "info" }];
  }
  if (status.last_error || (status.processed_frame_age_seconds ?? 0) > 3 || !status.continuous_frames_verified || (status.quality_flags?.length ?? 0) > 0) {
    return [{ id: "camera-unhealthy", title: "Check your camera", detail: "The camera signal may be interrupted or too old for current measurements.", suggestion: "Check the camera connection before relying on the numbers.", level: "attention" }];
  }
  if (status?.view_shift_detected && status.state === "LIVE") {
    return [{ id: "view-changed", title: "Camera view changed", detail: "The camera moved during this session, so spatial patterns cannot be compared reliably.", suggestion: "Fix the camera in place and restart monitoring to build a new consistent session.", level: "info" }];
  }
  const signals: ServiceSignal[] = [];
  const guestFiltered = status.staff_only_region && status.staff_only_region !== "none"
    && (status.automatic_insights?.guest_area_recent?.length ?? 0) > 0;
  const history: { people: number; at?: string }[] = guestFiltered
    ? status.automatic_insights!.guest_area_recent!.map((people) => ({ people }))
    : (status.people_count_history ?? []);
  // A comparison of sustained recent counts to earlier counts *within the same*
  // camera session; no arbitrary universal definition of a busy café.
  if (history.length >= 72) {
    // At the default 2 FPS, compare a sustained ~9s recent window against
    // an earlier ~15s baseline. Never convert counts into queue or order claims.
    const recent = history.slice(-18).map((p) => p.people);
    const earlier = history.slice(-72, -42).map((p) => p.people);
    const baseline = earlier.reduce((a, b) => a + b, 0) / earlier.length;
    const current = recent.reduce((a, b) => a + b, 0) / recent.length;
    const elevated = recent.filter((n) => n >= baseline + 2).length;
    // Guest-area history has counts only, unlike full-frame timestamped history.
    const recordedSpan = guestFiltered ? null : Date.parse(history.at(-1)?.at ?? "") - Date.parse(history[0]?.at ?? "");
    const enoughTime = guestFiltered ? (status.automatic_insights?.session_summary?.elapsed_seconds ?? 0) >= 30
      : recordedSpan != null && Number.isFinite(recordedSpan) && recordedSpan >= 30_000;
    if (enoughTime && current >= baseline + Math.max(2, baseline * 0.45) && elevated >= 15) {
      signals.push({ id: "activity-rising", title: "Visible activity is rising", detail: `The recent ${guestFiltered ? "guest-facing area" : "camera-view"} average is ${current.toFixed(1)} people, compared with ${baseline.toFixed(1)} earlier in this session.`, suggestion: "Check the actual counter or pickup area if relevant. Visible people alone do not prove a service backlog.", level: "attention" });
    }
  }
  const discoveredStays = status.automatic_insights?.scene_discovery?.hotspots.find(
    (item) => item.pattern === "longer_stays" && item.evidence === "strong",
  );
  if (discoveredStays) {
    signals.push({
      id: `scene-stays-${discoveredStays.id}`,
      title: "A consistently occupied area was observed",
      detail: `Low-movement activity was sampled around ${discoveredStays.location.toLowerCase()}. This may be one seated person, not repeat visits.`,
      suggestion: "This may simply be seating. Check the location before treating it as a waiting or service issue.",
      level: "info",
    });
  }
  const now = Date.now();
  for (const event of events) {
    if (event.type !== "possible_queue_buildup" || event.camera_id !== status.camera_id || event.state !== "active" || event.review_status === "false_alarm") continue;
    if (event.zone_id === "quick-waiting-area" || event.zone_id === "quick-whole-frame" || /starter|adjust location|full frame/i.test(event.zone_name)) continue;
    const when = Date.parse(event.started_at);
    if (!Number.isFinite(when) || Math.abs(now - when) > 120_000) continue;
    signals.push({ id: `queue-${event.zone_id}`, title: "Possible waiting-area pressure", detail: `A signal was generated for the configured ${event.zone_name} area.`, suggestion: "Check the area directly; people standing still do not always form a queue.", level: "attention" });
    break;
  }
  return signals;
}

export function ServiceSignalList({ signals, compact = false }: { signals: ServiceSignal[]; compact?: boolean }) {
  if (signals.length === 0) {
    return <div className="cafe-signal-empty"><CheckCircle2 size={22}/><div><strong>No immediate service signal</strong><p>FlowPulse has not found a sustained change that needs attention. Keep checking the floor as usual.</p></div></div>;
  }
  return <div className="cafe-signal-list">{signals.slice(0, compact ? 2 : 5).map((signal) => <article className={`cafe-signal cafe-signal-${signal.level}`} key={signal.id}>
    {signal.level === "attention" ? <CircleAlert size={21}/> : <Activity size={21}/>}
    <div><strong>{signal.title}</strong><p>{signal.detail}</p><small>{signal.suggestion}</small></div>
  </article>)}</div>;
}

export interface DesktopAlertControls {
  permission: NotificationPermission | "unsupported";
  enabled: boolean;
  toggle: () => Promise<void>;
}

/** Mounted at App root, not inside the Alerts page. Notifications continue
 * while the user browses Live café or Shift summary (app tab must stay open).
 */
export function useDesktopAlerts(status: Status | null, events: Observation[]): DesktopAlertControls {
  const [permission, setPermission] = useState<NotificationPermission | "unsupported">(
    typeof Notification === "undefined" ? "unsupported" : Notification.permission,
  );
  const [enabled, setEnabled] = useState(false);
  const sent = useRef(new Set<string>());
  const camera = status?.camera_id ?? "none";
  const signals = useMemo(() => deriveServiceSignals(status, events), [status, events]);
  useEffect(() => { sent.current.clear(); }, [camera]);
  useEffect(() => {
    if (status?.state === "OFFLINE" || status?.state === "PAUSED" || status?.preview_only) {
      sent.current.clear();
    }
  }, [status?.state, status?.preview_only]);
  useEffect(() => {
    if (!enabled || permission !== "granted" || typeof Notification === "undefined") return;
    for (const signal of signals.filter((item) => item.level === "attention")) {
      if (sent.current.has(signal.id)) continue;
      try {
        new Notification(`FlowPulse · ${signal.title}`, {
          body: signal.suggestion, tag: `flowpulse-${camera}-${signal.id}`,
        });
        sent.current.add(signal.id);
      } catch { /* Keep the on-screen alert even when the OS denies delivery. */ }
    }
  }, [enabled, permission, signals, camera]);
  async function toggle() {
    if (enabled) { setEnabled(false); return; }
    if (typeof Notification === "undefined") return;
    const result = await Notification.requestPermission();
    setPermission(result);
    setEnabled(result === "granted");
  }
  return { permission, enabled, toggle };
}

export function ServiceAlertsPage({ status, events, onCamera, desktop }: {
  status: Status | null; events: Observation[]; onCamera: () => void;
  desktop?: DesktopAlertControls;
}) {
  const signals = useMemo(() => deriveServiceSignals(status, events), [status, events]);
  const permission = desktop?.permission ?? "unsupported";
  const enabled = desktop?.enabled ?? false;
  return <div className="owner-page cafe-alert-page">
    <header className="owner-page-heading"><div><span className="owner-eyebrow">AUTOMATIC / SERVICE SIGNALS</span><h1>Know when to check in.</h1><p>FlowPulse watches for sustained changes and camera interruptions. No alert inbox to clear or manually label.</p></div><span className="owner-context-chip"><Bell size={15}/> Updates automatically</span></header>
    <section className="owner-panel cafe-alert-intro"><div><span className="owner-eyebrow">RIGHT NOW</span><h2>{signals.some((s) => s.level === "attention") ? "Something may need attention" : "You're up to date"}</h2><p>Only clear, evidence-based signals appear here. A notification suggests what to check; it never proves a customer is waiting.</p></div><div className="cafe-alert-count"><strong>{signals.filter((s) => s.level === "attention").length}</strong><span>active attention signals</span></div></section>
    <section className="owner-panel"><div className="owner-panel-heading"><div><span className="owner-eyebrow">SERVICE ATTENTION</span><h2>Only things that may need action</h2></div></div><ServiceSignalList signals={signals.filter((signal) => signal.level === "attention")}/></section>
    {signals.some((signal) => signal.level === "info") && <section className="owner-panel"><div className="owner-panel-heading"><div><span className="owner-eyebrow">INFORMATION · NO ACTION REQUIRED</span><h2>Patterns your camera has noticed</h2><p>Regular seating or longer stays are not automatically service problems.</p></div></div><ServiceSignalList signals={signals.filter((signal) => signal.level === "info")}/></section>}
    <section className="owner-panel cafe-notifications"><div><span className="owner-eyebrow">OPTIONAL / ON THIS DEVICE</span><h2>Desktop notifications</h2><p>Show a local browser notification for a new attention signal, even while viewing Live café or Shift summary. Keep this browser tab open. No video is uploaded.</p><small>{permission === "unsupported" ? "This browser does not support desktop notifications." : permission === "denied" ? "Notifications are blocked in your browser settings." : enabled ? "Enabled for this page session." : "Off by default; nothing is sent without your permission."}</small></div>
      <button className="owner-action-button" disabled={permission === "unsupported" || permission === "denied"} onClick={() => void desktop?.toggle()}>{enabled ? <BellOff size={16}/> : <Bell size={16}/>} {enabled ? "Turn off notifications" : "Enable notifications"}</button>
    </section>
    <section className="owner-panel cafe-alert-education"><div><Eye size={22}/><div><h2>No manual labels required</h2><p>Starter-zone observations and historical records are hidden from the owner's alerts. Basic alerts need no drawn zones. Accurate queue claims need a properly positioned and confirmed area.</p></div></div><button className="owner-link-button" onClick={onCamera}>Camera guidance <ArrowRight size={16}/></button></section>
    <p className="owner-fineprint"><ShieldCheck size={13}/> Alerts are suggestions based on local camera estimates, not diagnoses of customer intent or guaranteed staffing needs.</p>
  </div>;
}
