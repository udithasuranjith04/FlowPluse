import { Activity, Eye, HeartPulse, ShieldCheck, UsersRound } from "lucide-react";

/** Shown only while the first local backend status is being resolved.
 * It never implies that a camera has been opened or that inference is running.
 */
export function StartupScreen() {
  return (
    <main className="flowpulse-startup" aria-label="FlowPulse startup">
      <div className="startup-container">
        <div className="startup-brand"><span><HeartPulse size={24} /></span>flowpulse<sup>AI</sup></div>
        <section className="startup-presentation" aria-labelledby="startup-title">
          <div className="startup-copy">
            <span className="section-kicker">ANONYMOUS PEOPLE-FLOW INTELLIGENCE</span>
            <h1 id="startup-title">Understand spaces.<br /><em>Respect people.</em></h1>
            <p>Local guest-count trends and anonymous movement signals for cafés and restaurants—without identifying anyone.</p>
            <div className="startup-commitments">
              <span><ShieldCheck size={17} /> Local-only processing</span>
              <span><Eye size={17} /> No face recognition</span>
            </div>
          </div>
          <div className="startup-visual" aria-hidden="true">
            <div className="startup-ring startup-ring-one" />
            <div className="startup-ring startup-ring-two" />
            <UsersRound size={78} strokeWidth={1.15} />
            <span>PEOPLE · NOT IDENTITIES</span>
          </div>
        </section>
        <div className="startup-progress" role="status" aria-live="polite">
          <span className="startup-progress-icon"><Activity size={19} /></span>
          <div><strong>Connecting to your local workspace</strong><p>Reading backend status. Your camera will not start without permission.</p></div>
          <span className="startup-progress-indicator" aria-hidden="true" />
        </div>
        <p className="startup-footnote">Private by design · No cloud video processing</p>
      </div>
    </main>
  );
}
