import { Activity, ArrowRight, ChartNoAxesCombined, Clock3, ShieldCheck, UsersRound } from "lucide-react";
import type { Status } from "./types";

type SimpleStatus = Pick<Status, "ai_state" | "detection_target" | "preview_only" | "visible_people" | "people_count_history" | "tracks" | "processed_fps" | "automatic_insights">;

function formatDuration(seconds: number | null | undefined) {
  if (seconds == null || !Number.isFinite(seconds)) return "—";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const minutes = Math.floor(seconds / 60);
  const remaining = Math.round(seconds % 60);
  return remaining ? `${minutes}m ${remaining}s` : `${minutes}m`;
}

/** Detection counts are image-plane estimates, never a room census. */
export function SimpleInsights({ status, onAdvanced, onZones }: { status: SimpleStatus; onAdvanced: () => void; onZones: () => void }) {
  const live = status.ai_state === "active" && status.detection_target === "person";
  const data = live ? (status.people_count_history ?? []).filter((p) =>
    Number.isFinite(p.people) && p.people >= 0 && Number.isFinite(Date.parse(p.at))) : [];
  const latest = data.at(-1)?.people;
  const maximum = Math.max(1, ...data.map((p) => p.people));
  const coordinates = data.map((point, i) => {
    const x = data.length > 1 ? 12 + (i / (data.length - 1)) * 576 : 300;
    const y = 112 - (point.people / maximum) * 94;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  const auto = status.automatic_insights;
  const tracks = status.tracks?.filter((track) => track.label === "person").length ?? null;
  const paceLabel = live && auto?.service_level ? ({
    learning: "Learning",
    quiet: "Quiet",
    steady: "Steady",
    busy: "Busy",
    rush: "Rush",
  }[auto.service_level]) : "—";

  return <section className="studio-card simple-insights" aria-label="Automatic café insights">
    <div className="simple-insights-head"><div><span className="section-kicker">CAFÉ / AUTO PILOT</span>
      <h2>Café service pulse</h2>
      <p>Deeper trends update on their own. The numbers below describe the camera view, not identified customers.</p></div>
      <span className="simple-health"><ShieldCheck size={15}/>{status.preview_only ? "Preview · no events" : live ? "Local café monitoring active" : "Camera not ready"}</span>
    </div>
    <div className="simple-insights-stats">
      <div><UsersRound size={17}/><span>People in view now</span><strong>{live ? status.visible_people ?? "—" : "—"}</strong><small>Current processed frame</small></div>
      <div><ChartNoAxesCombined size={17}/><span>Anonymous tracks</span><strong>{live ? tracks ?? "—" : "—"}</strong><small>Anonymous live tracks</small></div>
      <div><Clock3 size={17}/><span>Longest visible person</span><strong>{live ? formatDuration(auto?.longest_visible_seconds) : "—"}</strong><small>Current anonymous track age</small></div>
      <div><Activity size={17}/><span>Processing rate</span><strong>{live ? `${status.processed_fps?.toFixed(1) ?? "—"} fps` : "—"}</strong><small>Observed backend throughput</small></div>
    </div>
    <details className="owner-auto-advanced"><summary><span><strong>See deeper automatic insights</strong><small>Guest patterns, image movement and measurement limits</small></span><ArrowRight size={17}/></summary>
    <div className="auto-summary" aria-label="Automatic service snapshot">
      <div className="auto-summary-top"><strong>Service snapshot</strong><span>Local · session only · no setup</span></div>
      <div className="auto-summary-grid">
        <div><span>Average people visible</span><strong>{live && auto?.average_visible != null ? auto.average_visible.toFixed(1) : "—"}</strong><small>Recent healthy frames</small></div>
        <div><span>Peak people visible</span><strong>{live ? auto?.peak_visible ?? "—" : "—"}</strong><small>Recent window, not store capacity</small></div>
        <div><span>Activity level</span><strong>{paceLabel}</strong><small>Rule-based estimate from people visible</small></div>
        <div><span>Long-visible tracks</span><strong>{live ? auto?.active_lingerers ?? "—" : "—"}</strong><small>Visible longer than 15 seconds</small></div>
        <div><span>Average live track age</span><strong>{live ? formatDuration(auto?.average_track_age_seconds) : "—"}</strong><small>Across current anonymous tracks</small></div>
        <div><span>Busiest view area</span><strong>{live ? auto?.busiest_image_sector ?? "Learning" : "—"}</strong><small>Image area, not a certified queue</small></div>
      </div>
      <div className="auto-crossings"><div><strong>Cross-view movement</strong><small>Only useful while the camera is stable</small></div>
        <div className="auto-crossings-metrics"><span>Left → right <strong>{live ? auto?.image_midline_crossings.left_to_right ?? "—" : "—"}</strong></span>
        <span>Right → left <strong>{live ? auto?.image_midline_crossings.right_to_left ?? "—" : "—"}</strong></span></div>
      </div>
      <p className="auto-disclaimer">These are image-plane estimates, not table turns, not exact queue length, and not certified occupancy. Long visible times describe anonymous tracks currently in the camera view only.</p>
    </div>
    </details>
    <div className="simple-trend"><div><div><strong>People visible over recent frames</strong>
      <small>Last {data.length} healthy frames · in-memory only · clears on stop or source change</small></div><span>{data.length ? `Latest ${latest}` : "Waiting for frames"}</span></div>
      {data.length >= 2 ? <svg viewBox="0 0 600 140" role="img" aria-label={`Count trend from ${data.length} frames, latest count ${latest}`} preserveAspectRatio="none">
        <path d="M12 18 H588 M12 65 H588 M12 112 H588" stroke="currentColor" opacity=".15" strokeDasharray="4 5" fill="none"/>
        <polyline points={coordinates} fill="none" stroke="#71e6c8" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
        <circle cx={Number(coordinates.split(" ").at(-1)?.split(",")[0] ?? 300)} cy={Number(coordinates.split(" ").at(-1)?.split(",")[1] ?? 112)} r="4" fill="#71e6c8"/>
      </svg> : <div className="trend-empty">{live ? "Collecting recent healthy frames…" : "Connect your camera to see actual guest activity."}</div>}
    </div>
    <div className="simple-insights-foot"><p>Guest counts, visible-track timing and the current session summary work automatically. Optional expert tools stay in Camera setup.</p>
      <div className="simple-insights-actions"><button className="studio-button secondary" onClick={onAdvanced}>View shift summary <ArrowRight size={15}/></button><button className="studio-button secondary" onClick={onZones}>Camera setup <ArrowRight size={15}/></button></div>
    </div>
  </section>;
}
