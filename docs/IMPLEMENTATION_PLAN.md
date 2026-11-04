# RoadPulse AI implementation plan

Source of truth: `ROADPULSE_BUILD_SPEC.md` (v1.0).

1. Foundation: local monorepo, typed settings/contracts, SQLite persistence, runnable development commands.
2. Pipeline: generated replay with an image-based synthetic detector, authorized live/file/snapshot adapters, optional YOLO11n CPU inference, anonymous tracking, bounded latest-frame capture, measured health.
3. Rules: validated monitoring/ignore polygons; stopped-vehicle and baseline-relative queue observations; quality suppression, lifecycle and cooldowns.
4. API: safe camera metadata, source activation, configuration, zones, events/reviews/export, metric series, local frames and WebSocket updates.
5. Dashboard: overview, events/details, polygon editor and thresholds, source permissions, diagnostics, About; accessible responsive dark UI.
6. Verification: deterministic backend and frontend tests, browser smoke tests, actual replay benchmark, CI, screenshots and setup/privacy/licensing documentation.
7. Delivery: meaningful local commits and push to the user's repository if network access and existing Git authentication permit.

## Decisions and assumptions

- No authorized camera URL or footage was supplied. First launch is explicitly **REPLAY**, using generated pixels. Synthetic detections are not evidence of real model accuracy. Live inference uses separately installed Ultralytics YOLO11n and locally downloaded weights.
- Repository code is AGPL-3.0-or-later to align with optional Ultralytics integration. No model weights or third-party footage are committed.
- This is a localhost application, without user accounts. Upstream URLs are environment-only; browser configuration never receives URLs or secrets. Source activation requires analysis and redisplay authorization. No arbitrary URL/path API exists.
- SQLite uses the standard-library driver, with parameterized queries and explicit transactions. Tracking uses a documented in-repository spatial association implementation; it is not advertised as ByteTrack.
- Evidence is disabled by default. Opt-in evidence is a redacted schematic reconstructed from detections (no original pixels), with TTL deletion.
- External-source accuracy evaluation and a permitted public live camera remain external prerequisites; no results or permissions will be invented.
- Initial environment: Python 3.12, Node 24; GitHub CLI is absent and shell DNS for GitHub failed. Credentials supplied in chat will not be stored or placed in commands.
