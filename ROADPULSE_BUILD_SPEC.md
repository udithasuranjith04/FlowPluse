# ROADPULSE AI — Complete Build Specification
**Version:** 1.0 | **Status:** Implementation-ready specification | **Target:** A polished, free-to-develop, local-first portfolio project

> **Instructions to the coding agent:** This document is the source of truth for implementing RoadPulse AI. Build a real working application, not a mockup. Do not invent camera URLs, permissions, performance results, or successful tests. If a requirement depends on an external stream or a user's credentials, provide a working adapter and explicit setup instructions rather than pretending it is configured.

---

## 1. Product vision

**RoadPulse AI** is a privacy-conscious, real-time road-condition observability dashboard. It consumes **authorized live public road-camera video**, detects and tracks vehicles, and highlights **potential road obstructions** and **sudden traffic buildup**. It explains why each event was flagged, lets the operator review evidence, and shows live system health.

This is a **portfolio/research demonstration**, not an emergency response, traffic enforcement, accident prediction, or official traffic-control system. No commercial features, payments, accounts, or paid APIs.

### Product promise
> Turn a live traffic camera into an understandable, evidence-based stream of road-condition observations.

### Explicit non-goals for v1
- No face recognition, plate OCR, person re-identification, or identifying individuals.
- No automatic claims that a collision, illegal act, or emergency occurred.
- No inferred real-world vehicle speeds or distances without calibration.
- No automated reporting to police or emergency services.
- No 24/7 hosting promise, no paid infrastructure, no scraping protected streams.
- No camera discovery through insecure camera indexes or bypassing access controls.
- No machine-learning training required for MVP.
- No multi-camera inference as a requirement; one reliable camera is enough.

## 2. Hard constraints and success criteria

**Budget:** $0 software/license/subscription cost for local development. Existing laptop/desktop, electricity, and internet are assumed; these are not literally free. A hosted always-on inference backend is **not** part of the $0 guarantee.

**Live requirement:** The main demo must support a genuine live video stream (HLS, MJPEG, or other FFmpeg/OpenCV-compatible authorized source). A static image that refreshes periodically must be labeled **snapshot mode** and cannot be treated as continuous tracking input. An MP4 fixture is permitted **only for offline development, tests, and fallback demonstration**, clearly labeled *replay*; it is never presented as live.

**Done means:**
1. A documented `make dev` or equivalent starts frontend and backend locally.
2. The operator can configure an approved camera URL using environment/config settings.
3. The UI shows the actual camera status, source type, last frame age, processing FPS, and whether input is LIVE / REPLAY / SNAPSHOT / OFFLINE.
4. On a live stream, detected vehicles receive boxes and short-lived anonymous track IDs.
5. The app produces explainable *potential stopped-vehicle* and *congestion buildup* observations, with configurable thresholds and cooldowns.
6. Events are persisted in local SQLite with timestamps, confidence/reasons, camera ID, and optional **redacted** evidence thumbnail only if retention is enabled.
7. A polished, responsive dashboard includes live view, event feed, analytics, camera/zone setup, and diagnostics.
8. A deterministic sample replay and automated tests prove the pipeline without external streams.
9. Privacy, licensing, camera permissions, limitations, and setup are documented.
10. CI runs lint, type checks, and tests; the repository contains no secrets or unlicensed footage.

## 3. Scope and priorities

### P0 — Must ship
- Single authorized live stream ingestion and reconnection.
- Vehicle detection: car, truck, bus, motorcycle (as supported by the chosen model).
- Vehicle tracking over time.
- Draw/edit lane or monitored road **polygons** in the dashboard; persist normalized coordinates per camera.
- **Potential stopped vehicle** rule based on a tracked vehicle remaining near-stationary inside a configured monitoring zone for a configurable duration.
- **Sudden congestion** rule based on increased lane occupancy / persistent count and reduced apparent movement relative to a local baseline.
- Real-time annotated stream or frequently updated frames with a transparent measured delay.
- Event list, details, evidence/reason, dismiss/acknowledge, and filter.
- Stream health and metrics.
- Replay mode for reproducible tests.
- README, screenshots/demo guide, CI, Docker optional but recommended.

### P1 — Nice to have after P0
- Multiple configured cameras with **one active inference worker** at a time.
- Configurable event severity (informational / review).
- Time-of-day summaries and chart.
- Redacted evidence snapshots with opt-in retention and automatic deletion.
- Export anonymized event metadata as CSV/JSON.
- Camera source attribution, terms link, and license status in UI.
- Optional CPU optimization via ONNX/OpenVINO, only after measuring a baseline.

### P2 — Future ideas, not part of MVP
- Crosswalk obstruction if the camera visibly includes a marked crosswalk and a human defines the polygon.
- Pedestrian–vehicle zone overlap as *potential interaction* requiring review, not near-miss prediction.
- Weather/flood/road debris detection only after a labeled evaluation dataset exists.
- Real-world distance/speed after camera calibration.
- Multi-camera map, historical comparison, public deployments.

## 4. User stories

1. **Viewer:** I open the dashboard and immediately see whether the video is actually live, where it comes from, and whether AI processing is active.
2. **Operator:** I draw a road-lane polygon and set thresholds without editing Python.
3. **Operator:** I can click an observation and see its time, camera, rule, duration, involved anonymous track IDs, and explanation.
4. **Reviewer:** I can acknowledge or mark an observation as a false alarm, preserving that label for evaluation.
5. **Developer:** I can run all tests and a deterministic demo with no network access or camera permissions.
6. **Recruiter:** I can understand the architecture, performance measurements, design decisions, and limitations in under five minutes.

## 5. UX/UI specification

### Visual direction
A professional **traffic operations dashboard**, not a generic admin template. Dark graphite/slate background, restrained cyan/teal live-data accent, amber review warnings, red only for actual stream failure. Clear typography, excellent contrast, subtle motion, crisp map-like overlays. Do not imitate a government agency or imply official status.

### Layout — desktop
- **Top navigation:** RoadPulse AI logo, `Research demo` label, selected camera, input mode (`LIVE`, `REPLAY`, `SNAPSHOT`, `OFFLINE`), pipeline state, last-frame timestamp, settings.
- **Primary content (~65–70% width):** Large 16:9 live video panel, overlays (bounding boxes, anonymous track IDs, zones, event markers), toggle overlays, frame timestamp, delay indicator, reconnect state. Use actual backend imagery; never substitute a stock image as a working camera.
- **Right rail (~30–35%):** Live observation timeline with severity, event name, timestamp, camera, short reason; selected event detail; acknowledge / false-alarm actions.
- **Below video:** KPI strip (active tracked vehicles, processed FPS, event count for current session, camera uptime, frame age). Clearly distinguish estimated counts from confirmed facts.
- **Lower panels:** Time-series occupancy chart, camera/source info, diagnostics and logs.
- **Navigation:** Overview, Events, Camera & Zones, Diagnostics, About.

### Mobile
Stack video above events; use a bottom sheet or separate route for event detail. Zone drawing may be desktop-only with an explanatory mobile message. No horizontal overflow.

### Required screens
**Overview**
- Live feed, connection health, overlay controls, observation timeline, KPIs, recent trend chart.
- Empty states: no camera configured; connecting; stream unavailable; AI loading; no events yet.

**Events**
- Filter by event type, status, date range and camera.
- Event detail: `Potential stopped vehicle`, `Congestion buildup`, reason, threshold, observed duration, time window, source, confidence/quality flags, redacted image if available.
- Actions: `Acknowledge`, `Mark false alarm`, `Reset review`.
- Use “potential”, “observed”, or “review” language; never “accident confirmed”.

**Camera & Zones**
- Camera configuration: display name, region, URL (backend-only; mask sensitive query tokens in UI/logs), stream type, provider, terms URL, reuse permission status, permission notes, enabled flag.
- Zone editor: pause on a recent frame, draw polygon with pointer, rename, choose `monitoring_lane` or `ignore`, save, delete, validate at least 3 points, show normalized coordinates.
- Controls: stationary threshold seconds, minimum track age, occupancy threshold, baseline window, cooldown seconds, min confidence, detection sampling FPS.
- Source health check: connect, show status, measured frame age and format.

**Diagnostics**
- Ingest FPS, processed FPS, inference latency p50/p95, dropped frames, reconnect count, last error, model name/version, CPU/GPU device, queue depth, event-rule debug values.
- Display honest measured values, never hardcoded metrics.

**About**
- What it detects, what it cannot detect, privacy policy, attribution, non-enforcement disclaimer, model license, repository link, demo mode disclosure.

### UI behaviors
- Skeletons only while real data loads; actionable error states with retry.
- Use WebSocket or SSE for metadata; serve processed JPEG frames via authenticated/local endpoint or a simple MJPEG endpoint. Never expose a private upstream camera token to the browser.
- Browser should display source state accurately if inference pauses or stream disconnects.
- Charts use real aggregated backend metrics; no fabricated sample analytics outside clearly marked demo/replay mode.
- Keyboard accessible controls, aria labels, visible focus rings, color-independent statuses.

## 6. Recommended technology stack

| Layer | Choice | Why |
|---|---|---|
| Frontend | React + TypeScript + Vite | Fast, polished, local-first SPA |
| Styling | Tailwind CSS + shadcn/ui or accessible headless primitives | Consistent UI, responsive design |
| Charts | Recharts | Simple metrics visualization |
| Icons | Lucide React | Clear operational icons |
| Backend | Python 3.11+ + FastAPI + Uvicorn | API, WebSockets, async orchestration |
| Video ingest | FFmpeg subprocess preferred; OpenCV VideoCapture fallback | HLS/MJPEG/RTSP support varies |
| Detection | Small pretrained YOLO-compatible detector | Fast vehicle classes, no training required |
| Tracking | ByteTrack (or equivalent) | Lightweight per-frame anonymous tracks |
| Geometry | OpenCV + NumPy + Shapely (optional) | Polygon checks and normalized coordinates |
| Persistence | SQLite + SQLAlchemy | Local and free |
| Configuration | Pydantic Settings + `.env` | Typed config and safe defaults |
| Testing | pytest + pytest-asyncio + Vitest + React Testing Library + Playwright smoke test | Verifiable functionality |
| Quality | Ruff, mypy or pyright, ESLint, Prettier | Reproducibility |
| Automation | GitHub Actions | Free within applicable GitHub usage limits |

**Licensing caution:** Check the actual license of the selected model implementation, model weights, tracker, and any pretrained weights. Ultralytics packages commonly use AGPL-3.0 and offer enterprise licensing; do **not** describe them as MIT/GPL-permissive. If selecting Ultralytics, document the AGPL implications for this repository and deployment. Use properly licensed assets, icons, and fonts.

## 7. Architecture

```text
Authorized live camera (HLS / MJPEG / RTSP)
               |
               v
       Camera Source Adapter
    - validate config and permission
    - reconnect with backoff
    - report timestamps/health
               |
               v
      Bounded Latest-Frame Queue
    - discard stale frames
    - avoid unbounded memory growth
               |
               v
        Detection Worker
    - sample configurable FPS
    - detect vehicle classes
               |
               v
          ByteTrack
    - anonymous per-session IDs
               |
               v
         Zone/Rule Engine
    - stationary vehicle rule
    - congestion buildup rule
    - cooldown, hysteresis, quality
               |
         +-----+------+
         |            |
         v            v
    SQLite events   Annotated frame cache
         |            |
         +------+-----+
                v
        FastAPI REST + WS
                |
                v
        React operations UI
```

**Concurrency:** Keep capture, inference, API, and UI concerns separate. The camera capture loop must not block API requests. Use a bounded queue of size 1–3 and drop old frames rather than building latency. Start with a single worker and a single active camera. Avoid GPU assumptions.

**Time:** Store UTC ISO 8601 timestamps; render local time in browser. Preserve both source timestamp (if reliable) and processing timestamp. Report end-to-end latency only if source timing is trustworthy; otherwise report **processing latency** and **frame age**, not falsely precise end-to-end delay.

**Security:** Reject local/private IP camera URLs by default if any public-facing URL configuration endpoint exists (SSRF protection); for local-only developer configuration, make the trust boundary explicit. Prefer allowlisted configured hosts. Never echo signed upstream URLs, tokens, or secrets to the frontend/logs. Bind local development services to localhost by default; enable CORS only for configured frontend origins. Rate-limit public endpoints if later deployed. Do not allow arbitrary filesystem paths through API.

## 8. Camera sourcing and legal gate

A camera being viewable on a public website does **not** automatically grant permission to record, transform, redistribute, or continuously query it.

### Required source onboarding
Before enabling any camera in a publicly shared demo, record:
- Provider/operator and official source page.
- Exact source format (true continuous video versus periodic JPEG).
- Evidence of authorization for **automated analysis**.
- Evidence of authorization for **retransmission/display** (if the frontend displays video).
- Access limits, attribution, retention, and geographic/legal conditions.
- Date permission was checked.
- Whether a direct URL is temporary, signed, or likely to expire.

**Suggested places to investigate, not preapproved feeds:**
- Caltrans CCTV documentation: https://cwwp2.dot.ca.gov/closed-circuit-television-cameras.html
- Maryland CHART camera viewer: https://chart.maryland.gov/TrafficCameras/GetTrafficCameras

Do not assume every feed at these portals is continuous video, supports automated processing, or permits republication. Verify each candidate before adding it to the shipped demo. If no qualifying live camera is available, ship the **working live adapter** plus replay-based demo, and state that the public live source remains unconfigured. Do not secretly replace the live requirement with snapshots or replay.

### Privacy by design
- No face/plate recognition or individual profiling.
- No raw footage storage by default; keep only event metadata.
- Evidence thumbnail storage **off by default**. If enabled, apply privacy masking before saving; masking failures should prevent storage, not save unredacted frames.
- Set retention TTL (e.g. 24 hours) and purge automatically when evidence storage is enabled.
- Avoid publishing individual pedestrian images or personally identifiable close-ups.
- No “fair use guarantees”; actual permission and applicable privacy law require checking.

## 9. Computer-vision pipeline specification

### 9.1 Frame ingest
- Support source adapters: `LiveStreamSource`, `ReplayFileSource`, and optional `SnapshotSource` with explicit capabilities.
- Use FFmpeg or OpenCV to decode frames; auto-reconnect with capped exponential backoff (1, 2, 4, 8, 15, 30 seconds).
- Stop/restart stream gracefully; release handles and subprocesses.
- Validate URL scheme, source type, frame dimensions, and timeout.
- Sample e.g. **2 FPS by default** for CPU; configurable after profiling. Do not promise 5–10 FPS on arbitrary laptops.
- Queue most recent frame only. Track dropped frame count.
- Camera health: CONNECTING, LIVE, STALE, RECONNECTING, OFFLINE, REPLAY, SNAPSHOT.

### 9.2 Detection
- Use a small pretrained detector with common vehicle classes.
- Filter allowed classes (`car`, `truck`, `bus`, `motorcycle`) and configurable confidence.
- Convert boxes to normalized coordinates for UI.
- Distinguish model confidence from confidence in the *event*. A detected vehicle does not mean a verified obstruction.

### 9.3 Tracking
- Assign short-lived anonymous track IDs **per stream session**.
- Store center/bottom-center positions and a rolling history with monotonic timestamps.
- Do not carry IDs across sessions or cameras.
- Ignore immature tracks until observed in enough frames / seconds.
- Handle occlusion, intermittent misses, and camera cuts; invalidate tracks after gap.
- Tracking requires continuous frames; disable temporal event rules in snapshot mode.

### 9.4 Zone rules
- Define polygons in normalized [0,1] coordinates.
- Test **bottom-center anchor** of vehicle bounding box against polygon (more meaningful for road contact than box center).
- Operators can define monitoring lanes and ignore zones.
- Ignore objects outside configured monitored areas.
- Require operator setup before enabling events; never infer lane legality automatically.

### 9.5 Rule A: Potential stopped vehicle
**Trigger conditions (initial tunable values, not validated):**
1. Vehicle track remains inside a monitoring-lane polygon.
2. Track is old enough (e.g. 8 seconds).
3. Smoothed image-plane anchor displacement is below a normalized threshold (e.g. 0.005 of frame diagonal per second) for at least 12 seconds.
4. The lane is not obviously in a general stop phase if the baseline or other tracks indicate traffic-wide stopping; otherwise suppress or downgrade.
5. Event passes a 60-second cooldown per track/zone.

**Output:** `potential_stopped_vehicle` with duration, zone, track ID, displacement metric, thresholds, quality flags and review status.

**Important:** A car stopped at a red light is not necessarily an obstruction. This is a **potential observation** only; include traffic-light/queue false-positive warnings. Do not claim real-world speed = 0 from pixel motion alone.

### 9.6 Rule B: Congestion buildup
**Inputs:** rolling count of tracked vehicles inside a monitoring polygon, estimated normalized occupancy (sum of box intersection areas with zone, clamped to avoid >100%), median image-plane motion, and a baseline over a configurable rolling window.

**Trigger:** Sustained occupancy increase and reduced motion relative to the same camera/zone baseline for e.g. 20 seconds. Use hysteresis (separate trigger/clear thresholds) and a cooldown. If the baseline has insufficient history, report `warming_up`, not a congestion alert.

**Output:** `congestion_buildup` with measured occupancy, count, baseline, change, window and confidence/quality notes.

**Limitations:** No absolute traffic-volume claim; occlusion, camera angle, signal phases and weather can bias metrics. For the first version, if the logic is not validated, call it `possible_queue_buildup` rather than “traffic jam confirmed”.

### 9.7 Event engine
- Deduplicate repeated triggers per camera/zone/rule/track.
- State machine: `candidate` → `active` → `resolved`; review state separately: `unreviewed`, `acknowledged`, `false_alarm`.
- Persist event start/end times, rule parameters, measured features, model version, source mode and input quality.
- Do not generate events from frozen/stale frames.
- If inference is too slow or frames drop excessively, flag low-quality input and suppress unreliable temporal alerts.

## 10. Data contracts and API

### Example event schema
```json
{
  "id": "uuid",
  "camera_id": "cam-1",
  "type": "potential_stopped_vehicle",
  "state": "active",
  "review_status": "unreviewed",
  "severity": "review",
  "started_at": "2026-10-31T09:00:00Z",
  "ended_at": null,
  "zone_id": "lane-east",
  "track_id": "session-4:17",
  "explanation": "Vehicle anchor motion remained below the configured image-plane threshold for 12 seconds in Lane East.",
  "features": {
    "stationary_seconds": 12.4,
    "motion_normalized_per_second": 0.002,
    "threshold": 0.005
  },
  "quality_flags": ["uncalibrated_camera"],
  "source_mode": "LIVE",
  "evidence_url": null
}
```
The example is **schema illustration**, not an actual detected event.

### REST
- `GET /api/health` — process health.
- `GET /api/system/status` — ingest/inference states, measured FPS, latency, last frame age, mode.
- `GET /api/cameras` — configured camera metadata, **redacted URLs**.
- `POST /api/cameras/{id}/activate` — select active configured source.
- `GET /api/cameras/{id}/zones` — polygons and rule config.
- `PUT /api/cameras/{id}/zones` — validated polygon config.
- `GET /api/events` — filters, pagination.
- `GET /api/events/{id}` — event detail.
- `PATCH /api/events/{id}/review` — acknowledge/false alarm/reset.
- `GET /api/metrics/series?window=...` — time series.
- `GET /api/stream/annotated.mjpg` — locally served processed frames, with source permission respected.
- `GET /api/config/public` — safe nonsecret configuration.

### WebSocket
- `WS /ws/live` — typed messages: `status`, `metrics`, `event_created`, `event_updated`, `event_resolved`.
- Reconnect client with backoff, display disconnected status, do not duplicate event entries.
- Version message schema or use discriminated `type` fields.

### Error contract
Use consistent JSON error payloads with machine-readable code, human-readable message and optional details. Validate camera IDs, polygons, thresholds and review actions. Return 400/404/409 as appropriate.

## 11. Suggested repository structure

```text
roadpulse-ai/
├── README.md
├── BUILD_SPEC.md
├── LICENSE
├── .gitignore
├── .editorconfig
├── .env.example
├── Makefile
├── docker-compose.yml             # optional local convenience
├── .github/
│   └── workflows/
│       └── ci.yml
├── docs/
│   ├── ARCHITECTURE.md
│   ├── CAMERA_SOURCES.md
│   ├── PRIVACY.md
│   ├── EVALUATION.md
│   ├── DEMO.md
│   └── DECISIONS.md
├── backend/
│   ├── pyproject.toml
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   ├── core/
│   │   ├── camera/
│   │   ├── vision/
│   │   ├── rules/
│   │   ├── models/
│   │   ├── storage/
│   │   └── schemas/
│   ├── tests/
│   │   ├── fixtures/
│   │   ├── test_camera.py
│   │   ├── test_tracking.py
│   │   ├── test_zones.py
│   │   ├── test_rules.py
│   │   ├── test_api.py
│   │   └── test_privacy.py
│   └── scripts/
│       ├── benchmark.py
│       └── make_synthetic_fixture.py
├── frontend/
│   ├── package.json
│   ├── index.html
│   ├── src/
│   │   ├── app/
│   │   ├── components/
│   │   │   ├── LiveFeed.tsx
│   │   │   ├── EventTimeline.tsx
│   │   │   ├── ZoneEditor.tsx
│   │   │   ├── StatusBar.tsx
│   │   │   └── MetricsCharts.tsx
│   │   ├── pages/
│   │   ├── hooks/
│   │   ├── lib/
│   │   └── types/
│   └── tests/
└── scripts/
    └── dev.sh
```

The exact structure may vary for clarity, but preserve separation of camera ingest, vision, event rules, API, and UI.

## 12. Configuration and developer experience

Provide `.env.example` with:
```dotenv
ROADPULSE_ENV=development
ROADPULSE_HOST=127.0.0.1
ROADPULSE_PORT=8000
ROADPULSE_DATABASE_URL=sqlite:///./roadpulse.db
ROADPULSE_CAMERA_MODE=replay
ROADPULSE_CAMERA_URL=
ROADPULSE_CAMERA_NAME=Demo Camera
ROADPULSE_CAMERA_PROVIDER=
ROADPULSE_CAMERA_SOURCE_PAGE=
ROADPULSE_CAMERA_TERMS_URL=
ROADPULSE_CAMERA_ANALYSIS_AUTHORIZED=false
ROADPULSE_CAMERA_REDISPLAY_AUTHORIZED=false
ROADPULSE_TARGET_FPS=2
ROADPULSE_MODEL_NAME=<documented-small-model>
ROADPULSE_SAVE_EVIDENCE=false
ROADPULSE_EVIDENCE_TTL_HOURS=24
ROADPULSE_ALLOWED_ORIGINS=http://localhost:5173
```
Replace the model placeholder with the actual chosen model in implementation and document download/license requirements. Never commit `.env`, camera secrets, weights with restricted redistribution, databases, or identifiable clips.

**Developer commands (implement these or equivalent):**
- `make setup` — install dependencies.
- `make dev` — start backend + frontend.
- `make test` — all backend/frontend unit tests.
- `make lint` — Python/TypeScript lint and type checks.
- `make demo` — deterministic synthetic replay.
- `make benchmark` — measure inference and processing throughput.

**First-run experience:** If no authorized live URL is configured, launch in clearly labeled **REPLAY DEMO** mode with a synthetic/generated fixture. Provide instructions for switching to a permitted live feed. Do not fail the entire app due to missing camera access.

## 13. Testing and evaluation

### Automated tests
- Geometry: normalized polygons, point-in-polygon, degenerate shapes, boundaries.
- Tracking: dropped frames, track expiration, camera cuts.
- Stationary rule: true stop, slow-moving vehicle, traffic light stop, short pause, no zone, stale frames.
- Congestion rule: baseline warmup, sustained buildup, brief spikes, clearing, low FPS, camera movement.
- Event state: dedupe, cooldown, candidate/active/resolved transitions.
- API: validation, pagination, review state changes, errors.
- Privacy: no URL token exposure, raw frame retention disabled, evidence write blocked on redaction failure.
- Frontend: status transitions, live/replay labeling, event list, zone editing, keyboard controls.
- Integration: synthetic frame stream → detector stub → tracker stub → rules → SQLite → API → UI.
- End-to-end smoke test: start demo and verify dashboard, event list and status.

### Evaluation protocol
1. Record **only permitted** evaluation footage or use properly licensed recorded datasets, plus synthetic fixtures.
2. Hand-label at least a modest representative set of event/non-event windows; include traffic-light stops, queues, night/rain, occlusion and camera interruptions.
3. Report **event-level** precision, recall and false alerts per hour; include sample size and confidence limitations.
4. Benchmark real measured CPU FPS, p50/p95 inference latency, memory and frame age on the developer's hardware.
5. Document failed cases and examples. Do not publish aspirational “95% accurate” claims.

### Suggested acceptance checks
- App launches from clean clone using README instructions.
- At least one event generated correctly in deterministic replay.
- No event from a frozen frame or snapshot source.
- Zones persist after restart.
- Review status persists after restart.
- No exposed camera token in API/UI/logs.
- Camera disconnect produces visible error and recovery attempt.
- Frontend responsive at ~375px and desktop.
- Tests pass locally and in CI.

## 14. Implementation milestones (4 weeks)

### Week 1 — Functional foundation
- Scaffold monorepo, GitHub CI, docs, .env.example.
- FastAPI + React skeleton; SQLite models.
- Live stream adapter with retry and measured health.
- Synthetic/replay fixture; vehicle detector working on actual frames.
- Dashboard shows source mode and real annotated frames.
**Gate:** actual detector works end to end on replay; live adapter can connect to an authorized stream when supplied.

### Week 2 — Tracking and first event
- Add tracker, anonymous IDs, zone editor and persistence.
- Implement stationary-vehicle rule and deterministic tests.
- Event timeline and event detail UI.
**Gate:** reproducible stopped-vehicle event and no alerts on stale frames.

### Week 3 — Second event and polish
- Congestion buildup with baseline and hysteresis.
- Diagnostics, measured FPS, chart, review actions.
- Camera permission metadata, privacy defaults and error states.
**Gate:** working UI from actual backend data; no mock numbers in production mode.

### Week 4 — Quality and public portfolio
- Label test clips and measure event metrics.
- Tune thresholds and suppress false alarms.
- Accessibility, mobile, loading/empty/error states.
- GitHub README with architecture diagram, screenshots, 60–120 sec demo, benchmarks and honest limitations.
- Verify a permitted live source or explicitly document the unresolved source requirement.
**Gate:** clean-clone setup, passing CI, honest demo, polished README.

## 15. GitHub setup and repository quality

**Suggested repository name:** `roadpulse-ai`

**Description:** `Privacy-conscious real-time road-condition monitoring from authorized public traffic cameras using computer vision.`

**Topics:** `computer-vision`, `traffic-monitoring`, `real-time`, `fastapi`, `react`, `python`, `object-tracking`, `portfolio-project`

**Visibility:** Public when no secrets, identifiable frames, or unlicensed assets are present.

**README must include:**
- Short product GIF or screenshot with LIVE/REPLAY mode clearly visible.
- Problem and solution; key features.
- Quick start, system prerequisites, CPU expectations.
- How to configure a permitted camera; source terms and permission process.
- Architecture and model/tracker choices.
- Demo and testing instructions.
- Real benchmark table with hardware and measured values (only after measurement).
- Accuracy/limitations, privacy policy, model/license notices.
- Roadmap and repository structure.

**Git practices:**
- Meaningful small commits, no giant unreviewable generated dump.
- `.gitignore` for `.env`, virtual environments, `node_modules`, model caches, SQLite databases, recordings, frames, logs, build outputs.
- CI checks on pull requests and pushes.
- Add GitHub repository URL to frontend About page only after repo exists.
- Do not commit any personal access token.

### Create and connect the repository manually
1. Create a **new empty** repository on GitHub named `roadpulse-ai` (do not initialize README if already created locally).
2. In the project directory:
```bash
git init
git add .
git commit -m "chore: initialize RoadPulse AI"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/roadpulse-ai.git
git push -u origin main
```
3. Replace `YOUR_USERNAME` with your actual GitHub username; authenticate using GitHub's supported authentication flow. Never put a token in a command or commit.
4. Alternatively, if GitHub CLI is installed and authenticated:
```bash
gh repo create roadpulse-ai --public --source=. --remote=origin --push
```
5. Verify the remote with `git remote -v` and confirm CI passes on GitHub.

**Agent rule:** If GitHub CLI/authentication is not available, do not claim the repository was created or pushed. Prepare the local repo and tell the user the exact next action.

## 16. Coding-agent execution protocol

**Do not stop at planning or UI mockups. Implement the product incrementally.**

1. Read this entire specification and inspect existing repository files.
2. Write a concise `docs/IMPLEMENTATION_PLAN.md` with ordered tasks and assumptions.
3. Create the backend, frontend and runnable local replay path.
4. Implement camera adapters and real detector/tracker; no fake live source.
5. Implement zones, rule engine, persistence and APIs.
6. Connect UI to actual backend and add all required states.
7. Add tests and CI; run them, fix failures, report commands/results.
8. Update README/docs, ensure licensing and camera permission controls.
9. Commit locally in meaningful milestones if git is configured.
10. Push to GitHub **only if** the user has explicitly authorized it and authentication is available; otherwise provide instructions.

**Never silently skip critical requirements.** If a dependency cannot be satisfied (e.g. camera permission, camera URL, compute capacity, package license), implement the safe fallback, record the blocker, and keep the status honest. Prioritize a tested vertical slice over breadth.

### Definition of a successful handoff
Provide a working repo, setup commands, tests and results, screenshots or a demo procedure, known limitations, and a clear statement of which live camera (if any) is configured and legally usable.

---

## 17. Short prompt to give Claude Code

Copy this after placing `BUILD_SPEC.md` in the repository:

> Read `BUILD_SPEC.md` fully and implement RoadPulse AI as a complete, working, polished portfolio application. Treat the spec as the source of truth. Start by creating `docs/IMPLEMENTATION_PLAN.md`, then build in small tested milestones: FastAPI backend, React/TypeScript dashboard, live-stream adapter, replay fallback, real vehicle detection/tracking, zone editor, stopped-vehicle and congestion rules, SQLite events, WebSocket updates, diagnostics, tests, CI and documentation. Use only free/local tools; never fake live data or performance results. Do not use any public camera without verified analysis/reuse permissions. Run tests and fix errors. Make meaningful git commits. If GitHub authentication is available, ask before creating/pushing the remote. Continue through the spec, reporting blockers honestly.

## 18. Suggested first action

Create the empty project directory and put this file at `BUILD_SPEC.md`. Open the folder in Claude Code and paste the short prompt above. If the coding agent needs one decision, prefer the simplest tested implementation consistent with this spec rather than asking for routine choices.

**Reminder:** This is a build specification, not evidence that any particular live feed, permission, model license, accuracy target, or free cloud host has been verified.
