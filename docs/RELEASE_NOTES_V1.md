# FlowPulse AI v1.0 — proposed portfolio release notes

**Status:** Release candidate. Publish the GitHub `v1.0.0` tag only after the final Mac acceptance checks. This file does not assert that the tag has already been created.

## What this release demonstrates

- Local-first Mac/iPhone/OBS Virtual Camera capture with explicit consent and safe preview/monitoring lifecycle.
- YOLO11n person detection on sampled real frames, short-lived anonymous spatial tracking, configurable people-flow zones and directional lines.
- Café owner view: live estimated people counts, an optional selected guest-facing image region, sustained high count, shift averages, count trend, automatic image-plane activity hotspots and carefully worded service-condition suggestions.
- FastAPI/SQLite backend, React/TypeScript frontend, local WebSocket updates and separated smooth preview versus slower AI inference.
- Confirmed versus unverified last-seen overlay styles, bounded expiry and explicit uncertainty in the UI.
- Privacy-conscious defaults: local processing, consent, no face recognition, and no raw footage storage by default.

## Validation status

The release review conducted against an uploaded source archive on **2026-11-05** ran the backend Python tests (180 passed, 2 skipped) and Python compilation. It did **not** run full Mac Ruff/mypy, frontend npm/Vitest/Playwright/build, live OBS capture, or manually labeled café accuracy. Record the final Mac results in the GitHub release description once performed. CI status is not yet verified.

## Important limitations

- Visible-people estimates are not customer-identification, actual occupancy census, unique visits, exact wait time or sales.
- Inference at a different FPS from video can cause visible overlay lag, even with smooth box transitions.
- Occlusion, perspective, stationary people, small background people, camera movement and tracking ID switches affect measurements.
- Hotspots indicate recurring image-plane presence/motion, not automatically identified café tables, queues or staffing problems.
- Only use video you have permission to process and redistribute. Label OBS video replay as prerecorded video processed live.

See [README](../README.md), [release checklist](RELEASE_CHECKLIST.md), [evaluation protocol](FLOWPULSE_EVALUATION.md), [licensing](LICENSING.md), and [café demo walkthrough](CAFE_DEMO.md).
