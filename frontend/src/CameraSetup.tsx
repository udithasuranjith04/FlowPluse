import { useEffect, useState } from "react";
import { Camera, CheckCircle2, CircleHelp, RefreshCw, ShieldCheck, Video } from "lucide-react";
import { api } from "./api";
import type { Status } from "./types";

interface LocalDevice { index: number; name: string; device_id?: string }
interface DeviceResponse { devices: LocalDevice[]; discovery_available?: boolean; message?: string }

/** Camera consent is explicit and scoped to the currently selected device. */
export function CameraSetup({ status, busy, activateLocal }: {
  status: Status | null;
  busy: boolean;
  activateLocal: (index: number, preview: boolean, deviceId?: string) => Promise<boolean>;
}) {
  const [devices, setDevices] = useState<LocalDevice[]>([]);
  const [device, setDevice] = useState<number | null>(null);
  const [consent, setConsent] = useState(false);
  const [listing, setListing] = useState(false);
  const [message, setMessage] = useState("");
  const [manual, setManual] = useState(false);
  const selected = devices.find((row) => row.index === device);
  const ownSession = device !== null && status?.camera_id === `local-camera-${device}`;
  const previewReady = ownSession && status?.preview_only === true &&
    status.ai_state === "active" && Boolean(status.frame_id) && Boolean(status.continuous_frames_verified);

  async function refreshDevices() {
    setListing(true);
    setMessage("");
    try {
      const response = await api<DeviceResponse>("/api/local-camera/devices");
      const rows = response.devices || [];
      setDevices(rows);
      setDevice((old) => rows.some((row) => row.index === old) ? old :
        (rows.find((row) => /iphone/i.test(row.name))?.index ?? rows[0]?.index ?? null));
      setConsent(false);
      setMessage(rows.length ? "Select the camera you control. For the best service insights, keep the counter or guest area in view. Device indices can change after reconnecting." :
        response.message || "No local camera was discovered. Check macOS Camera permissions.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not discover cameras.");
    } finally {
      setListing(false);
    }
  }
  useEffect(() => { void refreshDevices(); }, []);
  async function launch(preview: boolean) {
    if (!consent || device === null) return;
    await activateLocal(device, preview, selected?.device_id);
  }

  return <section className="studio-card camera-setup" aria-label="Local camera setup">
    <div className="card-topline">
      <span className="section-kicker">01 / INPUT</span>
      <span className="local-indicator"><ShieldCheck size={14} /> Local capture</span>
    </div>
    <div className="setup-head">
      <div>
        <h2>Connect your camera</h2>
        <p>Use your Mac camera or an iPhone Continuity Camera pointed at the permitted café floor, counter, or waiting area. No API keys, streaming services or uploaded footage.</p>
      </div>
      <button className="studio-icon-btn" aria-label="Refresh available cameras" onClick={() => void refreshDevices()} disabled={listing || busy}>
        <RefreshCw size={17} className={listing ? "spinning" : ""}/>
      </button>
    </div>
    <div className="camera-step">
      <label htmlFor="device-choice">Available camera</label>
      {devices.length ? <select id="device-choice" aria-label="Available camera device" value={device ?? ""}
        onChange={(event) => { setDevice(Number(event.target.value)); setConsent(false); }}>
        {devices.map((row) => <option value={row.index} key={row.device_id || row.index}>{row.name} · #{row.index}</option>)}
      </select> : <div className="device-missing">No camera listed. Refresh devices or enter a device index below.</div>}
      <button className="text-link" onClick={() => setManual(!manual)} aria-expanded={manual}>
        {manual ? "Hide manual index" : "Can't see your camera? Use an index"}
      </button>
      {manual && <label className="manual-index">Device index <input type="number" min="0" max="15" aria-label="Local camera device index" value={device ?? 0}
        onChange={(event) => { setDevice(Number(event.target.value)); setConsent(false); }}/></label>}
    </div>
    <label className="consent-tile">
      <input type="checkbox" checked={consent} onChange={(event) => setConsent(event.target.checked)} />
      <span><strong>I control this camera and authorize local analysis.</strong><small>I agree to display its video here and will use a permitted scene with informed participants.</small></span>
    </label>
    <div className="setup-actions">
      <button className="studio-button secondary" disabled={busy || listing || !consent || device === null || device < 0 || device > 15}
        onClick={() => void launch(true)}><Video size={16}/> Preview camera</button>
      <button className="studio-button primary" disabled={busy || !consent || !previewReady}
        onClick={() => void launch(false)}><Camera size={16}/> Start monitoring</button>
    </div>
    {ownSession && status?.preview_only && <div className="setup-feedback"><CheckCircle2 size={16}/>
      {previewReady ? "Live preview verified. Confirm the scene, then start monitoring." : "Opening preview; waiting for changing frames before monitoring can start."}
    </div>}
    {message && <p className="setup-message" role="status">{message}</p>}
    <div className="setup-note"><CircleHelp size={15}/> Preview never records observations. If the camera is unavailable, close QuickTime and allow Terminal access under macOS Camera settings.</div>
  </section>;
}
