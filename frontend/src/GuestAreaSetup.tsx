import { useEffect, useState } from "react";
import { ArrowRight, CheckCircle2, Info, ShieldCheck, UsersRound } from "lucide-react";
import { api } from "./api";
import type { Camera, StaffOnlyRegion, ZoneConfig } from "./types";

const choices: { value: StaffOnlyRegion; label: string; hint: string }[] = [
  { value: "none", label: "Show everyone", hint: "No staff-area filter" },
  { value: "left", label: "Left half", hint: "Staff work mainly at left" },
  { value: "right", label: "Right half", hint: "Staff work mainly at right" },
  { value: "top", label: "Back / top half", hint: "Staff counter is toward top" },
  { value: "bottom", label: "Near / bottom half", hint: "Staff area is near camera" },
];

/** Single operator-confirmed camera-region hint; not a classifier of individuals. */
export function GuestAreaSetup({ camera, onSave }: { camera: Camera; onSave: () => void }) {
  const [saved, setSaved] = useState<ZoneConfig | null>(null);
  const [choice, setChoice] = useState<StaffOnlyRegion>("none");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [frameToken, setFrameToken] = useState(0);
  useEffect(() => {
    let live = true;
    setSaved(null);
    setError("");
    api<ZoneConfig>(`/api/cameras/${encodeURIComponent(camera.id)}/zones`)
      .then((config) => { if (live) { setSaved(config); setChoice(config.staff_only_region ?? "none"); } })
      .catch((e: unknown) => { if (live) setError(e instanceof Error ? e.message : "Could not load camera settings."); });
    return () => { live = false; };
  }, [camera.id]);
  async function save() {
    if (!saved || busy || choice === (saved.staff_only_region ?? "none")) return;
    setBusy(true); setError(""); setMessage("");
    try {
      // Fetch the latest configuration so advanced zones/lines are never
      // silently overwritten when the operator changes a simple area hint.
      const current = await api<ZoneConfig>(`/api/cameras/${encodeURIComponent(camera.id)}/zones`);
      const updated = await api<ZoneConfig>(`/api/cameras/${encodeURIComponent(camera.id)}/zones`, {
        method: "PUT", body: JSON.stringify({ ...current, staff_only_region: choice }),
      });
      setSaved(updated);
      setMessage("Area saved. Session trends restart so old and new areas are not mixed.");
      onSave();
    } catch (e) { setError(e instanceof Error ? e.message : "Could not save this camera area."); }
    finally { setBusy(false); }
  }
  return <section className="owner-panel guest-area-setup" aria-label="Guest-facing area setup">
    <div className="guest-area-heading"><div><span className="owner-eyebrow">OPTIONAL · ONE-TIME CAMERA HINT</span>
      <h2>Does your camera also see behind the counter?</h2>
      <p>Choose the staff-only side of the picture. FlowPulse will automatically count people outside that side as <strong>people in the guest-facing area</strong>.</p></div><ShieldCheck size={25}/></div>
    <div className="guest-area-grid"><div className="guest-area-camera"><div className="guest-area-scene">
      <img src={`/api/stream/frame.jpg?overlays=false&camera_id=${encodeURIComponent(camera.id)}&reference=${frameToken}`} alt="Current camera reference for choosing a staff-only area" />
      {choice !== "none" && <div aria-hidden="true" className={`guest-area-mask guest-area-mask-${choice}`}>STAFF-ONLY SIDE<br/>EXCLUDED FROM GUEST-AREA ESTIMATE</div>}
    </div><div className="guest-area-picture-controls"><p>Darkened half is excluded from the guest-area estimate. This is a reference picture, not a live stream.</p><button onClick={() => setFrameToken((old) => old + 1)}>Refresh picture</button></div></div>
    <div className="guest-area-options"><label htmlFor="staff-region-choice">Which half is mostly staff-only?</label>
      <select id="staff-region-choice" value={choice} onChange={(e) => { setChoice(e.target.value as StaffOnlyRegion); setMessage(""); }} disabled={!saved || busy}>
        {choices.map((item) => <option key={item.value} value={item.value}>{item.label} — {item.hint}</option>)}
      </select>
      <button className="owner-action-button" disabled={!saved || busy || choice === (saved.staff_only_region ?? "none")} onClick={() => void save()}>{busy ? "Saving…" : "Save camera area"} <ArrowRight size={16}/></button>
      {message && <p className="guest-area-success" role="status"><CheckCircle2 size={16}/>{message}</p>}
      {error && <p role="alert" className="error-text">{error}</p>}
      <p className="guest-area-tip"><Info size={16}/> If staff and guests share the same half, leave Show everyone selected. This is not automatic staff recognition.</p>
    </div></div>
    <p className="guest-area-footnote"><UsersRound size={16}/> No uniforms, face recognition, identity tracking, employee profiles or personal role labels. The camera cannot know who is a customer; location is only a rough counting hint.</p>
  </section>;
}
