import { useEffect, useState } from "react";
import { Check, Crosshair, Plus, RotateCcw, Save, Trash2 } from "lucide-react";
import { api } from "./api";
import type { Camera, Rules, ZoneConfig } from "./types";

const flowFields: {
  key: keyof Rules;
  label: string;
  min: number;
  max: number;
  step: number;
  unit: string;
}[] = [
  { key: "flow_dwell_seconds", label: "Dwell observation duration", min: 2, max: 600, step: 1, unit: "seconds" },
  { key: "flow_queue_people", label: "Possible queue minimum people", min: 2, max: 100, step: 1, unit: "people" },
  { key: "flow_queue_seconds", label: "Possible queue duration", min: 2, max: 600, step: 1, unit: "seconds" },
  { key: "flow_motion_threshold", label: "Low motion threshold", min: 0.0001, max: 0.1, step: 0.001, unit: "diagonal / second" },
  { key: "flow_slow_fraction", label: "Low motion fraction", min: 0.5, max: 1, step: 0.05, unit: "fraction" },
  { key: "flow_capacity", label: "Illustrative zone capacity", min: 1, max: 500, step: 1, unit: "people" },
  { key: "flow_crossing_margin", label: "Crossing hysteresis", min: 0.002, max: 0.1, step: 0.002, unit: "fraction of image" },
  { key: "flow_crossing_cooldown", label: "Crossing cooldown", min: 0.1, max: 30, step: 0.5, unit: "seconds" },
  { key: "flow_track_maturity_seconds", label: "Person track maturity", min: 0.5, max: 30, step: 0.5, unit: "seconds" },
  { key: "min_confidence", label: "Detector confidence", min: 0.1, max: 0.95, step: 0.05, unit: "model score" },
  { key: "target_fps", label: "Frame processing", min: 0.5, max: 15, step: 0.5, unit: "frames per second" },
];

const fields: {
  key: keyof Rules;
  label: string;
  min: number;
  max: number;
  step: number;
  unit: string;
}[] = [
  {
    key: "stationary_seconds",
    label: "Stationary duration",
    min: 2,
    max: 300,
    step: 1,
    unit: "seconds",
  },
  {
    key: "min_track_age",
    label: "Minimum track age",
    min: 1,
    max: 120,
    step: 1,
    unit: "seconds",
  },
  {
    key: "motion_threshold",
    label: "Motion threshold",
    min: 0.0001,
    max: 0.1,
    step: 0.0001,
    unit: "diagonal / second",
  },
  {
    key: "occupancy_threshold",
    label: "Occupancy threshold",
    min: 0.01,
    max: 0.9,
    step: 0.01,
    unit: "fraction of zone",
  },
  {
    key: "occupancy_increase",
    label: "Occupancy increase",
    min: 0.01,
    max: 0.8,
    step: 0.01,
    unit: "above baseline",
  },
  {
    key: "baseline_window",
    label: "Baseline window",
    min: 5,
    max: 600,
    step: 1,
    unit: "seconds",
  },
  {
    key: "congestion_seconds",
    label: "Buildup duration",
    min: 2,
    max: 300,
    step: 1,
    unit: "seconds",
  },
  {
    key: "cooldown_seconds",
    label: "Observation cooldown",
    min: 1,
    max: 3600,
    step: 1,
    unit: "seconds",
  },
  {
    key: "min_confidence",
    label: "Detection confidence",
    min: 0.1,
    max: 0.95,
    step: 0.05,
    unit: "model score",
  },
  {
    key: "target_fps",
    label: "Detection sampling",
    min: 0.5,
    max: 15,
    step: 0.5,
    unit: "frames / second",
  },
];

export default function ZoneEditor({
  camera,
  onSave,
  people = false,
}: {
  camera: Camera;
  onSave: () => void;
  people?: boolean;
}) {
  const [config, setConfig] = useState<ZoneConfig | null>(null);
  const [points, setPoints] = useState<[number, number][]>([]);
  const [drawing, setDrawing] = useState<"zone" | "line">("zone");
  const [lineName, setLineName] = useState("Front-door entry");
  const [name, setName] = useState(people ? "Counter waiting area" : "New monitoring lane");
  const [kind, setKind] = useState<"monitoring_lane" | "ignore">(
    "monitoring_lane",
  );
  const [editId, setEditId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [saving, setSaving] = useState(false);
  const [frame, setFrame] = useState(Date.now());
  const [frameAvailable, setFrameAvailable] = useState(true);
  const [x, setX] = useState(0.5),
    [y, setY] = useState(0.5);
  useEffect(() => {
    let active = true;
    setConfig(null);
    setPoints([]);
    setEditId(null);
    api<ZoneConfig>(`/api/cameras/${camera.id}/zones`)
      .then((c) => {
        if (active) setConfig(c);
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [camera.id]);
  function addPoint(point: [number, number]) {
    setPoints((old) => (old.length < (drawing === "line" ? 2 : 40) ? [...old, point] : old));
    setMessage("");
  }
  function commitLine() {
    if (!config || points.length !== 2 || !lineName.trim()) {
      setError("Set exactly two line endpoints and a name.");
      return;
    }
    const [[ax, ay], [bx, by]] = points;
    if (Math.hypot(ax - bx, ay - by) < 0.02) {
      setError("Line must have meaningful length.");
      return;
    }
    setConfig({
      ...config,
      lines: [...(config.lines ?? []), {
        id: `line-${crypto.randomUUID().slice(0, 8)}`,
        name: lineName.trim(),
        points: [points[0], points[1]],
      }],
    });
    setPoints([]);
    setError("");
    setMessage("Counting line added to draft. Save configuration to activate.");
  }
  function commitPolygon() {
    if (!config || points.length < 3 || !name.trim()) {
      setError("Add at least 3 points and a name.");
      return;
    }
    const zone = {
      id: editId || `zone-${crypto.randomUUID().slice(0, 8)}`,
      name: name.trim(),
      kind,
      points,
    };
    setConfig({
      ...config,
      zones: [...config.zones.filter((z) => z.id !== editId), zone],
    });
    setPoints([]);
    setEditId(null);
    setError("");
    setMessage("Polygon added to draft. Save configuration to apply.");
  }
  async function applyPreset(preset: "whole-frame" | "waiting-area" | "entry-line") {
    if (!config || saving) return;
    if (points.length) {
      setError("Clear or finish your drawing before using a quick preset.");
      return;
    }
    const next = { ...config, zones: [...config.zones], lines: [...(config.lines ?? [])] };
    if (preset === "entry-line") {
      if (next.lines.some((line) => line.id === "quick-entry-line")) {
        setMessage("The starter line already exists. Delete it to replace it, or draw your own.");
        return;
      }
      // This is a centered template, NOT a detected doorway.
      next.lines.push({ id: "quick-entry-line", name: "Starter entrance line · adjust to doorway", points: [[0.15, 0.5], [0.85, 0.5]] });
    } else {
      const id = preset === "whole-frame" ? "quick-whole-frame" : "quick-waiting-area";
      if (next.zones.some((zone) => zone.id === id)) {
        setMessage("That preset already exists. You can edit or delete its polygon below.");
        return;
      }
      next.zones.push({ id, name: preset === "whole-frame" ? "Dining floor" : "Starter counter waiting area · adjust location",
        kind: "monitoring_lane", points: preset === "whole-frame"
          ? [[0.01, 0.01], [0.99, 0.01], [0.99, 0.99], [0.01, 0.99]]
          : [[0.25, 0.25], [0.75, 0.25], [0.75, 0.85], [0.25, 0.85]] });
    }
    setSaving(true);
    setError("");
    try {
      const saved = await api<ZoneConfig>(`/api/cameras/${camera.id}/zones`, {
        method: "PUT", body: JSON.stringify(next),
      });
      setConfig(saved);
      setMessage(preset === "entry-line"
        ? "Starter line saved. Align it with the real entrance before trusting crossing counts."
        : preset === "whole-frame"
          ? "Full-frame count-only zone saved. No dwell or queue alerts are generated for it."
          : "Starter waiting area saved. Adjust it to the real counter or pickup area before interpreting dwell or queue observations.");
      onSave();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Preset save failed");
    } finally { setSaving(false); }
  }
  async function save() {
    if (!config) return;
    if (points.length) {
      setError(
        "Add the current polygon to the draft, or clear it before saving.",
      );
      return;
    }
    setSaving(true);
    setError("");
    try {
      await api(`/api/cameras/${camera.id}/zones`, {
        method: "PUT",
        body: JSON.stringify(config),
      });
      setMessage("Configuration saved. Observation baselines restarted.");
      onSave();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }
  if (!config)
    return (
      <div className="panel empty" role="status">
        {error || "Loading monitoring configuration…"}
      </div>
    );
  return (
    <div className="setup-grid">
      <section className="panel zone-panel">
        <div className="panel-heading">
          <div>
            <h2>{people ? "Define optional service zones and counting lines" : "Define the road area"}</h2>
            <p>
              {people ? "Draw a waiting area or service zone for dwell and queue observations, or a two-point line for entry and exit counts." : "Draw a polygon on a paused frame. Only monitored areas generate observations."}
            </p>
          </div>
          <button
            className="icon-button"
            aria-label="Refresh paused frame"
            onClick={() => {
              setFrame(Date.now());
              setFrameAvailable(true);
            }}
          >
            <RotateCcw size={16} />
          </button>
        </div>
        <div
          className="zone-canvas"
          style={{ minHeight: frameAvailable ? undefined : 260 }}
        >
          <img
            src={`/api/stream/frame.jpg?overlays=false&camera_id=${encodeURIComponent(camera.id)}&t=${frame}`}
            alt="Paused camera frame for drawing monitoring zones"
            onError={() => setFrameAvailable(false)}
            hidden={!frameAvailable}
          />
          {!frameAvailable && (
            <div className="empty">
              No recent frame. Activate this source, then refresh.
              <br />
              Normalized coordinates can still be entered below.
            </div>
          )}
          <svg
            viewBox="0 0 1000 1000"
            preserveAspectRatio="none"
            aria-label="Zone drawing canvas"
            onClick={(e) => {
              if (!frameAvailable) return;
              const r = e.currentTarget.getBoundingClientRect();
              if (drawing === "line" && points.length >= 2) return;
              addPoint([
                Number(((e.clientX - r.left) / r.width).toFixed(4)),
                Number(((e.clientY - r.top) / r.height).toFixed(4)),
              ]);
            }}
          >
            {config.zones
              .filter((z) => z.id !== editId)
              .map((z) => (
                <polygon
                  key={z.id}
                  points={z.points
                    .map(([a, b]) => `${a * 1000},${b * 1000}`)
                    .join(" ")}
                  className={
                    z.kind === "ignore" ? "ignore-polygon" : "saved-polygon"
                  }
                />
              ))}
            {people && (config.lines ?? []).map((line) => <line
              key={line.id}
              x1={line.points[0][0] * 1000} y1={line.points[0][1] * 1000}
              x2={line.points[1][0] * 1000} y2={line.points[1][1] * 1000}
              stroke="#46d9b5" strokeWidth={5} />)}
            <polyline
              points={points
                .map(([a, b]) => `${a * 1000},${b * 1000}`)
                .join(" ")}
              className="draft-polygon"
            />
            {points.map(([a, b], i) => (
              <circle key={i} cx={a * 1000} cy={b * 1000} r="7" />
            ))}
          </svg>
          <span className="canvas-label">
            <Crosshair size={13} /> REFERENCE FRAME · {points.length} POINTS
          </span>
        </div>
        {people && <div className="quick-presets" aria-label="Quick spatial setup">
          <div className="quick-presets-heading"><div><strong>Quick café setup</strong><p>Optional. These are editable geometry templates, not AI-detected entrances or waiting areas.</p></div><span>ONE CLICK</span></div>
          <div className="quick-presets-actions">
            <button disabled={saving} onClick={() => void applyPreset("whole-frame")}>Use dining floor</button>
            <button disabled={saving} onClick={() => void applyPreset("waiting-area")}>Add counter waiting area</button>
            <button disabled={saving} onClick={() => void applyPreset("entry-line")}>Add starter entry line</button>
          </div>
          <p>The dining-floor preset is count-only: it will not generate dwell or queue alerts. For those observations, use a specific waiting area near the counter or pickup zone. Starter lines are templates, not AI-detected doorways.</p>
        </div>}
        <div className="zone-controls">          {people && <div className="button-row" role="group" aria-label="Drawing mode">
            <button className={drawing === "zone" ? "selected" : ""} onClick={() => { setDrawing("zone"); setPoints([]); }}>Draw service zone</button>
            <button className={drawing === "line" ? "selected" : ""} onClick={() => { setDrawing("line"); setPoints([]); }}>Draw two-point counting line</button>
          </div>}
          {people && drawing === "line" ? <>
            <label>Counting line name<input aria-label="Counting line name" value={lineName} maxLength={80} onChange={(e) => setLineName(e.target.value)} /></label>
            <p className="muted small">Click the frame twice to set a directed line. Movement from the negative to positive side counts as an entry; reversing direction counts as an exit. Use a stable camera and deliberate direction.</p>
          </> : <div className="form-row">
            <label>
              Zone name
              <input
                maxLength={80}
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </label>
            <label>
              Zone type
              <select
                value={kind}
                onChange={(e) => setKind(e.target.value as typeof kind)}
              >
                <option value="monitoring_lane">{people ? "Service monitoring zone" : "Monitoring lane"}</option>
                <option value="ignore">Ignore area</option>
              </select>
            </label>
          </div>}

          <p className="muted small">
            Click the frame to place points, or use coordinates below.
            Coordinates range from 0 to 1.
          </p>
          <div className="coordinate-row">
            <label>
              X
              <input
                type="number"
                min="0"
                max="1"
                step=".01"
                value={x}
                onChange={(e) => setX(Number(e.target.value))}
              />
            </label>
            <label>
              Y
              <input
                type="number"
                min="0"
                max="1"
                step=".01"
                value={y}
                onChange={(e) => setY(Number(e.target.value))}
              />
            </label>
            <button
              onClick={() =>
                addPoint([
                  Math.max(0, Math.min(1, x)),
                  Math.max(0, Math.min(1, y)),
                ])
              }
            >
              <Plus size={14} />
              Add point
            </button>
          </div>
          <div className="button-row">
            <button
              onClick={() => setPoints((p) => p.slice(0, -1))}
              disabled={!points.length}
            >
              Undo point
            </button>
            <button
              onClick={() => {
                setPoints([]);
                setEditId(null);
              }}
            >
              Clear draft
            </button>
            <button
              className="primary"
              onClick={people && drawing === "line" ? commitLine : commitPolygon}
              disabled={people && drawing === "line" ? points.length !== 2 : points.length < 3}
            >
              <Check size={15} />
              {people && drawing === "line" ? "Add counting line" : editId ? "Update polygon" : "Add polygon"}
            </button>
          </div>
          {points.length > 0 && (
            <code className="coordinates">
              {points.map((p) => `(${p.join(", ")})`).join(" · ")}
            </code>
          )}
          <div className="zones-list">
            {config.zones.map((zone) => (
              <div key={zone.id} className="zone-row">
                <span className={`zone-dot ${zone.kind}`} />
                <div>
                  <strong>{zone.name}</strong>
                  <small>
                    {zone.kind.replace("_", " ")} · {zone.points.length} points
                  </small>
                </div>
                <button
                  onClick={() => {
                    setEditId(zone.id);
                    setName(zone.name);
                    setKind(zone.kind);
                    setPoints(zone.points);
                  }}
                >
                  Edit
                </button>
                <button
                  className="icon-button"
                  aria-label={`Delete ${zone.name}`}
                  onClick={() =>
                    setConfig({
                      ...config,
                      zones: config.zones.filter((z) => z.id !== zone.id),
                    })
                  }
                >
                  <Trash2 size={15} />
                </button>
              </div>
            ))}
          </div>
          {people && <div className="zones-list" aria-label="Counting lines">
            {(config.lines ?? []).map((line) => <div key={line.id} className="zone-row">
              <div><strong>{line.name}</strong><small>Directed counting line · two endpoints</small></div>
              <button aria-label={`Reverse counting line ${line.name}`} onClick={() => {
                setConfig({ ...config, lines: (config.lines ?? []).map((item) => item.id === line.id
                  ? { ...item, points: [item.points[1], item.points[0]] } : item) });
                setMessage("Line direction reversed in draft. Save configuration to activate.");
              }}>Reverse direction</button>
              <button className="icon-button" aria-label={`Delete counting line ${line.name}`} onClick={() => setConfig({ ...config, lines: (config.lines ?? []).filter((l) => l.id !== line.id) })}><Trash2 size={15}/></button>
            </div>)}
          </div>}
          {!config.zones.length && (
            <p className="notice">
              {people ? "No service zones yet. Add one for dwell or queue observations; a separate line enables directional counts." : "No zones. Temporal observations are disabled until a monitoring lane is saved."}
            </p>
          )}
        </div>
      </section>
      <section className="panel thresholds">
        <div className="panel-heading">
          <div>
            <h2>{people ? "Service-signal thresholds" : "Observation thresholds"}</h2>
            <p>Initial research values. Tune against reviewed footage.</p>
          </div>
        </div>
        <div className="threshold-fields">
          {(people ? flowFields : fields).map((f) => (
            <label key={f.key}>
              {f.label}
              <div>
                <input
                  aria-label={f.label}
                  type="number"
                  min={f.min}
                  max={f.max}
                  step={f.step}
                  value={config.rules[f.key]}
                  onChange={(e) =>
                    setConfig({
                      ...config,
                      rules: {
                        ...config.rules,
                        [f.key]: Number(e.target.value),
                      },
                    })
                  }
                />
                <span>{f.unit}</span>
              </div>
            </label>
          ))}
        </div>
        <div className="save-area">
          {error && (
            <p role="alert" className="error-text">
              {error}
            </p>
          )}
          {message && (
            <p role="status" className="success-text">
              {message}
            </p>
          )}
          <button
            className="primary full"
            onClick={() => void save()}
            disabled={saving}
          >
            <Save size={16} />
            {saving ? "Saving…" : "Save configuration"}
          </button>
        </div>
      </section>
    </div>
  );
}
