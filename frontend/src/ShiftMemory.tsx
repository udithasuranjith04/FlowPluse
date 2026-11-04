import { useEffect, useState } from "react";
import { Database, LockKeyhole, Trash2 } from "lucide-react";
import { api } from "./api";
import type { Status } from "./types";

interface SavedShift { created_at: string; processed_samples: number; elapsed_seconds: number; average_visible: number; peak_visible: number }
interface ShiftMemoryState { enabled: boolean; saved_shifts: SavedShift[]; retention_days: number; minimum_samples: number; minimum_duration_seconds?: number }
/** Optional aggregate-only retention; persisted on this Mac, never on an external service. */
export function ShiftMemory({ status }: { status: Status | null }) {
  const [saved, setSaved] = useState<ShiftMemoryState | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { let active = true; api<ShiftMemoryState>("/api/privacy/shift-memory")
    .then((data) => { if (active) setSaved(data); }).catch((e) => { if (active) setError(e instanceof Error ? e.message : "Could not read shift memory."); });
    return () => { active = false; }; }, [status?.camera_id, status?.staff_only_region]);
  async function update(enabled: boolean) {
    setBusy(true); setError("");
    try { const result = await api<ShiftMemoryState>("/api/privacy/shift-memory", { method: "PUT", body: JSON.stringify({ enabled }) }); setSaved(result); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not update settings."); }
    finally { setBusy(false); }
  }
  const shifts = saved?.saved_shifts ?? [];
  const current = status?.automatic_insights?.session_summary?.average_visible;
  const sortedMeans = shifts.map((row) => row.average_visible).sort((a, b) => a - b);
  const middle = Math.floor(sortedMeans.length / 2);
  const baseline = sortedMeans.length >= 3
    ? sortedMeans.length % 2 ? sortedMeans[middle] : (sortedMeans[middle - 1] + sortedMeans[middle]) / 2
    : null;
  const elapsed = status?.automatic_insights?.session_summary?.elapsed_seconds ?? 0;
  const comparableNow = elapsed >= (saved?.minimum_duration_seconds ?? 240) && !status?.view_shift_detected;
  return <section className="owner-panel shift-memory" aria-label="Optional shift memory">
    <div className="shift-memory-head"><Database size={23}/><div><span className="owner-eyebrow">OPTIONAL · LOCAL SHIFT MEMORY</span><h2>Compare one shift with previous shifts</h2><p>Off by default. Save only anonymous session averages and peaks for up to 30 days—never video, photos, faces or tracks. Use a fixed camera viewpoint: saved sessions cannot verify that the camera angle stayed the same between days.</p></div></div>
    <div className="shift-memory-tools"><button disabled={busy || !saved} className="studio-button secondary" onClick={() => void update(!saved?.enabled)}>{saved?.enabled ? "Turn off and erase shift history" : "Enable local aggregate memory"}</button><span><LockKeyhole size={15}/> {saved?.enabled ? `${shifts.length} previous shifts saved` : "No shift history is retained"}</span></div>
    {saved?.enabled && (baseline == null ? <p className="shift-memory-learning">Building a local reference: save at least 3 completed sessions with the same camera and area. Sessions need 300 healthy frames and 4 minutes; this is still not a verified café baseline.</p> : <div className="shift-memory-comparison"><strong>{comparableNow && current != null ? `${current.toFixed(1)} average now · ${current >= baseline ? "+" : ""}${(current - baseline).toFixed(1)} vs reference` : "Collect 4 minutes of stable monitoring before comparing"}</strong><span>Median of {shifts.length} previous compatible records: {baseline.toFixed(1)} people visible (range {sortedMeans[0].toFixed(1)}–{sortedMeans.at(-1)!.toFixed(1)}). Same camera ID and area setting only; the app cannot prove that the viewpoint or business hours match.</span></div>)}
    {error && <p role="alert" className="error-text">{error}</p>}
    <p className="owner-fineprint"><Trash2 size={13}/> Turning this off immediately deletes all stored shift summaries. Session-only live numbers still work.</p>
  </section>;
}
