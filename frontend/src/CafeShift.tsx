import { ArrowDownToLine, ArrowRight, Clock3, Coffee, Lightbulb, ShieldCheck, TrendingUp, UsersRound } from "lucide-react";
import type { Status } from "./types";
import { ShiftMemory } from "./ShiftMemory";

function formatElapsed(seconds: number) {
  if (seconds < 60) return `${Math.max(0, Math.round(seconds))} sec`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} min`;
  return `${Math.floor(minutes / 60)}h ${minutes % 60}m`;
}

type Point = { minute: number; average: number };
export function shiftDirection(points: Point[]) {
  if (points.length < 4) return { label: "Learning", detail: "More shift time is needed to compare periods.", rising: false };
  const earlier = (points[0].average + points[1].average) / 2;
  const recent = (points.at(-2)!.average + points.at(-1)!.average) / 2;
  const threshold = Math.max(1.5, earlier * 0.3);
  if (recent - earlier > threshold) return { label: "Busier", detail: `Recently ${recent.toFixed(1)} people in view vs ${earlier.toFixed(1)} earlier. Check whether the counter needs support.`, rising: true };
  if (earlier - recent > threshold) return { label: "Calmer", detail: `Recently ${recent.toFixed(1)} people in view vs ${earlier.toFixed(1)} earlier.`, rising: false };
  return { label: "Steady", detail: "The sampled counts have not shifted much across the observed shift.", rising: false };
}

/** An honest shift-style view: session aggregates only, no invented daily history. */
export function CafeShift({ status, onCamera }: { status: Status | null; onCamera: () => void }) {
  const live = status?.detection_target === "person" && status.ai_state === "active" && !status.preview_only;
  const candidate = live ? status?.automatic_insights?.session_summary : null;
  const summary = candidate?.processed_samples ? candidate : null;
  const points = summary?.minute_averages ?? [];
  const direction = shiftDirection(points);
  const longest = status?.automatic_insights?.longest_visible_seconds;
  const supportedPeak = summary && "supported_peak_visible" in summary
    ? summary.supported_peak_visible : summary?.peak_visible;
  const peakOutlier = Boolean(summary?.peak_possible_outlier);
  const highest = Math.max(1, ...points.map((point) => point.average));
  const y = (n: number) => 128 - n / highest * 94;
  const coordinates = points.map((p, index) => `${40 + index * (540 / Math.max(1, points.length - 1))},${y(p.average)}`).join(" ");
  const csv = ["minute_since_start,mean_people_visible", ...points.map((p) => `${p.minute},${p.average}`)].join("\n");
  return <div className="owner-page">
    <header className="owner-page-heading"><div><span className="owner-eyebrow">SHIFT PULSE</span><h1>What did your camera see this shift?</h1><p>Automatically summarized from actual monitoring frames. No recording or manual entries needed.</p></div><span className="owner-context-chip"><Clock3 size={15}/> This session only</span></header>
    {status?.view_shift_detected && <div className="studio-warning" role="status">Camera movement was detected during this session. Counts after that movement are a fresh partial sample; this session will not be saved in shift memory. Restart with a fixed view for reliable comparisons.</div>}
    <div className="owner-summary-grid">
      <div className="owner-summary-card"><UsersRound size={20}/><span>Average people in view</span><strong>{summary?.average_visible ?? "—"}</strong><small>Includes staff if visible · not visitor totals</small></div>
      <div className="owner-summary-card"><TrendingUp size={20}/><span>Sustained high count</span><strong>{supportedPeak ?? "Learning"}</strong><small>Five-sample median · not certified occupancy</small></div>
      <div className="owner-summary-card"><TrendingUp size={20}/><span>Activity direction</span><strong>{summary ? direction.label : "—"}</strong><small>Compared across this session · never an external benchmark</small></div>
      <div className="owner-summary-card"><Clock3 size={20}/><span>Time monitored</span><strong>{summary ? formatElapsed(summary.elapsed_seconds) : "—"}</strong><small>Since current camera monitoring began</small></div>
    </div>
    {summary && <p className="shift-evidence-note">Based on {summary.processed_samples} healthy processed frames across {formatElapsed(summary.elapsed_seconds)}. Raw single-frame maximum: {summary.peak_visible ?? "—"}.{peakOutlier ? " An unusually high single-frame count may be a duplicate or false detection." : " The sustained high requires several nearby observations."} Partial minutes and occlusion can change these estimates.</p>}
    {status?.staff_only_region && status.staff_only_region !== "none" && summary && <section className="owner-panel guest-area-shift"><ShieldCheck size={23}/><div><span className="owner-eyebrow">GUEST-FACING AREA ESTIMATE</span><h2>Average people outside the staff-only side: {summary.guest_area_average ?? "—"}</h2><p>Peak in that area: {summary.guest_area_peak ?? "—"}. These are people in the selected area, not verified customers or completed visits. Full-camera shift totals remain above.</p></div></section>}
    <section className="owner-split"><div className="owner-panel owner-chart-card"><div className="owner-panel-heading"><div><span className="owner-eyebrow">ACTIVITY OVER TIME</span><h2>People visible during this shift</h2><p>Minute averages, not arrivals, orders or sales.</p></div>{summary && <a className="owner-export-link" download="flowpulse-shift-minutes.csv" href={`data:text/csv;charset=utf-8,${encodeURIComponent(csv)}`}><ArrowDownToLine size={16}/> Export CSV</a>}</div>
      {points.length >= 2 ? <div className="owner-chart-wrap"><svg viewBox="0 0 600 170" className="owner-shift-chart" role="img" aria-label={`Guest count averages across ${points.length} session minutes`} preserveAspectRatio="none"><path d="M40 34 H580 M40 81 H580 M40 128 H580" stroke="currentColor" opacity=".18" strokeDasharray="4 6" fill="none"/><polyline points={coordinates} stroke="#61d8bb" strokeWidth="3" strokeLinejoin="round" strokeLinecap="round" fill="none"/><text x="10" y="37" fill="currentColor" fontSize="12">{highest.toFixed(0)}</text><text x="19" y="132" fill="currentColor" fontSize="12">0</text><text x="40" y="155" fill="currentColor" fontSize="12">0 min</text><text x="580" y="155" textAnchor="end" fill="currentColor" fontSize="12">{points.at(-1)!.minute} min</text></svg></div> : <div className="owner-chart-empty"><Coffee size={30}/>{summary ? "The minute-by-minute chart will grow as this shift continues." : "Start monitoring to collect real shift data."}</div>}
      <div className="owner-chart-footer"><span>{summary ? `${summary.processed_samples} processed frames in this session` : "No monitoring session yet"}</span><span>Local · anonymous · resets on stop</span></div>
    </div><aside className="owner-panel owner-decision-panel"><span className="owner-eyebrow"><Lightbulb size={15}/> HOW TO USE THIS</span><h2>{!summary ? "Start with your camera" : direction.rising ? "Activity is picking up" : direction.label === "Calmer" ? "The floor is getting quieter" : direction.label === "Learning" ? "Learning your shift's pattern" : "A steady shift so far"}</h2><p>{!summary ? "Choose and preview a permitted camera, then start monitoring. Your shift summary appears automatically." : direction.detail}</p><p className="cafe-shift-guidance">Compare these numbers with staff coverage and actual orders. The camera alone cannot measure service speed or customer satisfaction.</p><button className="owner-action-button" onClick={onCamera}>{!summary ? "Connect camera" : "Review camera setup"}<ArrowRight size={16}/></button><div className="owner-trust-line"><ShieldCheck size={15}/> No people identified or stored as customer profiles.</div></aside></section>
    <details className="owner-advanced-disclosure cafe-auto-details"><summary><span><TrendingUp size={19}/><strong>More automatic movement details</strong><small>Already calculated from the live camera; no manual zones needed.</small></span><ArrowRight size={19}/></summary>
      <div className="owner-advanced-content"><div className="cafe-more-metrics"><div><span>Most active image area</span><strong>{status?.automatic_insights?.busiest_image_sector ?? "Learning"}</strong><small>Where people were seen in the frame, not a confirmed queue or service point</small></div>
        <div><span>Across-image movement</span><strong>{status?.automatic_insights?.image_midline_crossings?.left_to_right ?? "—"} → / {status?.automatic_insights?.image_midline_crossings?.right_to_left ?? "—"} ←</strong><small>Centerline crossings; not physical café entries and exits</small></div>
        <div><span>Longest visible track</span><strong>{longest == null ? "—" : formatElapsed(longest)}</strong><small>How long an anonymous track stayed visible; not customer waiting time</small></div></div></div></details>
    <ShiftMemory status={status}/>
    <p className="owner-fineprint">This is a live-session summary, not an all-day business report. It resets on camera stop or source change. The exported CSV contains only minute-level average counts.</p>
  </div>;
}
