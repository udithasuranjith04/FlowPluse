# FlowPulse Studio — frontend and domain cleanup

## Goal
Present a meaningful privacy-first people-flow application, not a
synthetic-vehicle application with new branding.

## Changed
- The main interface is now a responsive **Live overview / Observations /
  Zones & lines / System health / About** workspace.
- No auto-playing traffic footage in ordinary `make dev`.
- Dedicated `CameraSetup` uses the existing local camera discovery, consent,
  preview and activation endpoints. Start is gated on changed-frame verification.
- People-flow observations and exports use `domain=people` at the API/database
  layer. The old data is preserved; an opt-in archive toggle reveals it.
- Retired the unused road snapshot, traffic measurement, and provider-selection
  React modules. Backwards-compatible backend provider endpoints remain for
  existing clients and tests.
- Replaced obsolete frontend tests and Playwright scenarios with privacy-safe,
  source-oriented ones. Physical iPhone acceptance is still opt-in.

## Migration for existing Macs
1. Back up the entire existing FlowPulse folder, including `.env` and
   `runtime/` privately. Do not upload them.
2. Apply the studio patch at repository root: `patch --dry-run -p1 < ...`,
   then `patch -p1 < ...` if clean.
3. In `.env` set `ROADPULSE_DETECTION_TARGET=person` and
   `ROADPULSE_AUTOSTART=false`. Existing `ROADPULSE_` names remain intentional.
4. Run `make lint`, `make test`, `make build`, then `make dev`.
5. In the dashboard, refresh devices, select the iPhone, check the consent
   box, preview, verify changing frames, and start monitoring. Configure a zone
   and counting line to enable spatial events.

## Acceptance gates
- `make lint`: Ruff, Python typing, ESLint and TypeScript clean.
- `make test`: backend domain and people-flow rules; frontend device consent,
  dashboard, zone editor and live-status handling.
- `make build`: Vite production compilation.
- `make verify-people` while monitoring: confirms changed frames and reports
  person detections, but **does not prove real-world accuracy**.
- Optional `FLOWPULSE_LIVE_E2E=1` Playwright run on an authorized Mac camera.

## Honest limitations
Automated tests and a successful build are not a real-camera evaluation.
Actual false positives, missed detections, track ID switches, directional
counting errors, queue indicators, latency, macOS camera permission, and mobile
layout should be evaluated on the user's Mac before any portfolio accuracy
claim. No face recognition, persistent person identity or footage retention is
required. Keep the service localhost-only.
