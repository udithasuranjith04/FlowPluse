# FlowPulse AI contributor guidance

FlowPulse Studio is a **privacy-first people-flow application**. Read `README.md`, `docs/ARCHITECTURE.md`, `docs/STUDIO_UPGRADE.md`, and `docs/FLOWPULSE_EVALUATION.md` before modifying it. The historical `ROADPULSE_BUILD_SPEC.md` describes archived traffic functionality, not the current product scope. For release hygiene, follow `docs/RELEASE_CHECKLIST.md` and `scripts/release_prep.py`.

- Python backend lives in `backend/app/`; API entrypoint is `app.main:app` on 127.0.0.1:8000.
- React/TypeScript frontend lives in `frontend/src/`; Vite runs at 127.0.0.1:5173. Prefer `make dev` (camera not auto-started). `make demo` is **legacy vehicle fixture only**.
- Keep person inference restricted to COCO person class; do not add face recognition, demographics, identity persistence or unconsented camera feeds.
- Use explicit operator consent, camera preview, single active capture/inference pipeline, bounded latest-frame queue and correct device release. Camera continuity is required before temporal measurements.
- Do not silently mix archived vehicle events into people-flow metrics. Retain source provenance and honest snapshot/fixture labels in backend compatibility routes.
- Keep `.env`, video, model weights, camera URLs, secrets, local DBs and raw frames out of version control. Use the existing ignore rules. Preserve user data and configuration when applying migrations.
- Keep observation lifecycle separate from human review labels. Reset track IDs and temporal rules after stop/source changes or stale input.
- Run `make lint`, `make test`, and `make build` for substantive changes; a successful suite does not validate real-camera accuracy. Record genuine acceptance results in docs only after running them.
- Never invent a benchmark, permission, screenshot, frame, model download or test outcome.
