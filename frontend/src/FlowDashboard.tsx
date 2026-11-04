import { Activity, ArrowDownToLine, ArrowUpFromLine, Clock3, Users } from "lucide-react";
import type { Status } from "./types";

export function FlowDashboard({ status, onZones }: {
  status: Status;
  onZones: () => void;
}) {
  const metrics = status.flow;
  if (!metrics) return <section className="panel flow-overview">People-flow analytics are unavailable for this source.</section>;
  const zones = Object.entries(metrics.zone_counts);
  const enabled = status.temporal_rules_enabled && status.ai_state === "active";
  const configured = Boolean(metrics.lines.length || Object.keys(metrics.zone_counts).length);
  const stateLabel = status.preview_only ? "PREVIEW · NO EVENTS" : !configured
    ? "NO SPATIAL BOUNDARIES" : enabled ? "SPATIAL MONITORING" : "SPATIAL RULES INACTIVE";
  return <section className="panel flow-overview" aria-label="People flow analytics">
    <div className="panel-heading">
      <div>
        <h2>People flow · current session</h2>
        <p>Anonymous image-plane counts, not identified individuals. Crossing directions follow the configured line orientation.</p>
      </div>
      <span className="badge">{stateLabel}</span>
    </div>
    <div className="flow-counters">
      {([
        ["People visible", status.visible_people ?? "—", Users],
        ["Entries", metrics.entries, ArrowDownToLine],
        ["Exits", metrics.exits, ArrowUpFromLine],
        ["Processed FPS", status.processed_fps.toFixed(1), Activity],
      ] as const).map(([label, value, Icon]) => <div className="flow-counter" key={label}>
        <span><Icon size={17} />{label}</span><strong>{value}</strong>
      </div>)}
    </div>
    {zones.length ? <div className="flow-zones">
      {zones.map(([id, count]) => <div className="flow-zone" key={id}>
        <span>{id.replaceAll("_", " ")}</span><strong>{count} in zone</strong>
      </div>)}
    </div> : <p className="muted">No monitoring polygon yet. Whole-frame person detection is already available in Simple mode.</p>}
    <div className="flow-footer">
      <span><Clock3 size={15} /> {metrics.lines.length} counting lines configured. Counts reset on stops, source changes or discontinuities.</span>
      <button className="button" onClick={onZones}>Configure zones and lines</button>
    </div>
    <p className="muted small">Whole-frame presets are count-only. Dwell and possible-queue candidates require a smaller area of interest and sustained evidence. Neither indicates a person's intentions; review before use.</p>
  </section>;
}
