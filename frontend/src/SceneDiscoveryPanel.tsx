import { Activity, BrainCircuit, Coffee, Footprints, ShieldCheck, Timer } from "lucide-react";
import type { SceneDiscovery, SceneHotspot, Status } from "./types";

const descriptions: Record<SceneHotspot["pattern"], { label: string; detail: string; Icon: typeof Activity }> = {
  longer_stays: {
    label: "Sustained low movement",
    detail: "A tracked person remained with little motion here. This may simply be seating, not a service delay.",
    Icon: Timer,
  },
  movement: {
    label: "Movement activity",
    detail: "Anonymous track motion was sampled here. This is not a verified service route.",
    Icon: Footprints,
  },
  frequent_presence: {
    label: "Frequent presence",
    detail: "People were visible in many sampled frames. A single stationary person can produce this pattern.",
    Icon: Activity,
  },
};

export function SceneDiscoveryPanel({ status, compact = false }: { status: Status | null; compact?: boolean }) {
  const live = status?.detection_target === "person" && status.ai_state === "active" && !status.preview_only && status.state === "LIVE";
  const viewChanged = Boolean(status?.view_shift_detected);
  const scene: SceneDiscovery | null = live && !viewChanged && status ? status.automatic_insights?.scene_discovery ?? null : null;
  const suggestions = scene?.hotspots ?? [];
  const ready = scene?.state === "ready" && suggestions.length > 0;
  const frame = live && status?.frame_id && status?.camera_id;
  const ratio = status?.resolution?.length === 2 && status.resolution[1] > 0
    ? `${status.resolution[0]} / ${status.resolution[1]}` : "16 / 9";
  return <section className={`owner-panel cafe-scene-discovery ${compact ? "is-compact" : ""}`} aria-label="Automatic scene discovery">
    <div className="owner-panel-heading"><div><span className="owner-eyebrow"><BrainCircuit size={15}/> AUTOMATIC SCENE INTELLIGENCE</span>
      <h2>Where is activity happening?</h2>
      <p>FlowPulse learns recurring activity locations from anonymous movement and presence. No zones to draw or clothing rules to set.</p></div>
      <span className="scene-learning-chip">{viewChanged ? "View changed" : ready ? "Patterns found" : "Learning scene"}</span>
    </div>
    <div className="scene-discovery-layout">
      <div className="scene-map-wrap"><div className={`scene-map ${frame ? "scene-map-video" : ""}`} style={frame ? { aspectRatio: ratio } : undefined} role="img" aria-label={ready ? `Camera view activity map with ${suggestions.length} discovered areas` : "Empty camera activity map while the scene is learning"}>
        {frame ? <img className="scene-map-frame" src={`/api/stream/frame.jpg?overlays=false&camera_id=${encodeURIComponent(status!.camera_id)}&frame_id=${encodeURIComponent(status!.frame_id!)}&view=activity-map`} alt=""/> : <div className="scene-grid" aria-hidden="true">{Array.from({ length: 24 }, (_, index) => <span key={index}/>)}</div>}
        {suggestions.map((item, index) => <div key={item.id} className={`scene-hotspot scene-hotspot-${item.pattern}`} style={{ left: `${item.bounds[0] * 100}%`, top: `${item.bounds[1] * 100}%`, width: `${(item.bounds[2] - item.bounds[0]) * 100}%`, height: `${(item.bounds[3] - item.bounds[1]) * 100}%` }} aria-hidden="true"><strong>{index + 1}</strong></div>)}
        <div className="scene-map-top"><Coffee size={15}/> {frame ? "Hotspots over your camera view" : "Camera image coordinates, not a floor plan"}</div>
        <div className="scene-map-bottom">{ready ? `${scene?.sampled_frames} healthy monitored frames · recent sample` : viewChanged ? "View changed · restart monitoring" : live ? "Gathering repeated activity to discover patterns" : "Start monitoring to learn the view"}</div>
      </div>
      <div className="scene-map-explainer">
        <strong>How to read this</strong>
        <span>Boxes show areas of recurring visibility or motion—not tables, customer groups, or service queues.</span>
        {scene && <span>{Math.round(scene.window_seconds)} seconds of recent monitoring · {scene.sampled_frames} processed frames</span>}
        <span>One fixed view is required for meaningful comparisons.</span>
      </div></div>
      <div className="scene-discovery-findings">
        {ready ? suggestions.map((item, index) => {
          const { label, detail, Icon } = descriptions[item.pattern];
          return <article className="scene-finding" key={item.id}>
            <div className="scene-finding-icon"><Icon size={17}/></div>
            <div><div className="scene-finding-title"><strong>{index + 1}. {label}</strong><span>{item.evidence === "strong" ? "Well sampled" : "Emerging"}</span></div>
              <small>{item.location}</small><p>{detail}</p>
              <span className="scene-evidence">Seen in {item.frames_with_people} sampled frames · {item.visible_now} visible here now</span>
              {item.observed_seconds != null && <span className="scene-evidence-secondary">Visible for approximately {item.observed_seconds.toFixed(0)}s of this sample · {item.occupancy_episodes ?? "—"} occupancy periods, not distinct visits</span>}
            </div>
          </article>;
        }) : <div className="scene-learning-state"><BrainCircuit size={30}/><strong>{viewChanged ? "Camera view changed" : live ? "Learning from the camera" : "Automatic discovery starts with monitoring"}</strong>
          <p>{viewChanged ? "This camera moved during monitoring. Stop, fix it in place, and restart to learn one consistent view." : live ? "Keep the camera fixed. The map will appear after enough healthy frames show a repeatable pattern." : "Preview and authorize a camera first. Preview alone never builds activity profiles."}</p>
          {live && !viewChanged && <small>{scene?.sampled_frames ?? 0} healthy monitoring frames sampled</small>}
        </div>}
      </div>
    </div>
    <div className="scene-discovery-foot"><ShieldCheck size={17}/><p>These are activity hotspots, <strong>not automatic staff/customer recognition</strong>. One person appearing in many frames is not repeat visitors. No clothing, faces or identities are used. A longer stay does not prove a queue or waiting time.</p></div>
  </section>;
}
