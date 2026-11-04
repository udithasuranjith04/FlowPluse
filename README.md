# FlowPulse AI

**Privacy-conscious people-flow analytics, running locally on your Mac.** A local camera feeds YOLO11n person detections, temporary anonymous tracking, people-in-zone estimates, entry/exit counting, and reviewable dwell/possible-queue observations to a React/FastAPI dashboard.

This repository **evolves the existing RoadPulse AI implementation**. It retains its existing backend architecture, legacy traffic demonstration, camera adapters, WebSocket updates, SQLite storage and tests. Existing backend endpoints and the `ROADPULSE_` environment variable prefix remain unchanged for compatibility. It is a **research/portfolio application, not a certified people counter or a security system**.

## What is implemented

- **Real live owned camera:** macOS AVFoundation device discovery, iPhone Continuity Camera when macOS exposes it, explicit owner consent, preview, start/pause/stop, and capture worker isolation. No phone streaming app or paid API required.
- **Person-only inference:** YOLO11n, COCO class 0, on real frames. Old generated demo is explicitly vehicle-based and remains a separate fixture.
- **Anonymous per-session tracking:** lightweight spatial matching with a short gap timeout; tracking resets on source interruptions, changing configuration or session changes.
- **People-flow rules:** occupancy of a configured polygon by tracked footpoint; directional crossings across an oriented two-point line; sustained zone dwell events; possible queue buildup from several low-motion people. Rules are disabled for static snapshots and preview, and suspend when frame quality is insufficient.
- **Interactive editor:** define per-camera monitoring/ignore polygons and two-point counting lines; tune flow durations, motion threshold, queue size, debounce and model confidence.
- **Dashboard:** camera image with authentic inference overlays, visible count, entry/exit counters, per-zone occupancy, event review/archive, pipeline measurements and camera error states.
- **Privacy:** local-only FastAPI, no raw footage retention by default, no face recognition or cross-session persistent identity. Events contain metadata and short-lived track IDs; do not use this with unconsenting people or in settings without appropriate notice/permission.

## FlowPulse Studio interface (new)

The main UI is now **camera-first**. Launching `make dev` starts the API and
React dashboard **without automatically activating the historical synthetic
road-traffic fixture**. The dashboard defaults to a safe offline state until a
local camera is explicitly selected and authorized.

- **Live overview:** local camera discovery, device selection by stable ID,
  explicit consent, preview-only verification, start monitoring, real detection
  frames, people-visible counts, crossings, processing FPS and recent events.
- **Observations:** dwell and possible-queue records only by default;
  historical vehicle-fixture records can be revealed deliberately. CSV export
  observes the same backend domain filter rather than silently mixing records.
- **Zones & lines:** the existing per-camera normalized polygon and directed
  line editor, with people-flow threshold configuration.
- **System health:** actual backend pipeline measurements, input continuity,
  device state, zone-rule debugging and error logs.
- **About:** privacy and evaluation limitations.

Old road snapshot, provider and traffic components have been retired from the
**frontend**. The backend legacy adapters, SQL records and event engine remain
for compatibility and regression tests; no user data is deleted. The synthetic
vehicle fixture is an explicit **`make demo`** developer option, not the
people-flow dashboard's default input. Do not present it as person-detection
validation.

## Quick start — macOS

**Requirements:** macOS with access to a camera you control (or an authorized OBS Virtual Camera), Python **3.12**, Node.js **22.12+**, npm, and Git. Model inference runs locally. Source code does not include YOLO weights, camera footage, database contents, or a trained café-specific model.

```sh
# Clone your own GitHub repository, then enter its project directory.
# On a fresh clone only:
make setup
make model

# For a previously configured Mac installation, keep .venv and .env;
# do not rerun setup or recreate your local model/data unnecessarily.

make lint
make test
make build
make dev
```

Open **http://127.0.0.1:5173**. Select your permitted Mac/iPhone/OBS camera, confirm consent, verify the changing preview, then explicitly start monitoring. The dashboard does **not** auto-start a camera. `make dev` uses localhost-only services (API: `http://127.0.0.1:8000/docs`). Exit with **Control+C**. If port 5173 or 8000 is occupied, stop the previous local development server instead of launching a second copy.

For local configuration use `.env.example` as a reference. On a new install, create `.env` only if it does not exist. The compatibility `ROADPULSE_` prefix is intentional. Do **not** commit `.env`, local footage, customer data, database files, downloaded model weights, or private screenshots. Some optional features require a permitted fixed camera view and further scene-specific testing. See [owner guide](docs/CAFE_OWNER_GUIDE.md), [architecture](docs/ARCHITECTURE.md), and [Mac acceptance checklist](docs/RELEASE_CHECKLIST.md).

**Existing RoadPulse installations:** Keep the existing virtual environment, runtime data and `.env`. The source migration instructions are archived in [FlowPulse migration](docs/FLOWPULSE_MIGRATION.md); they are not required to clone a clean FlowPulse repository.

## Configure people-flow measurement

On **Zones & lines**, choose the owned camera and:

1. Create a **People monitoring zone** polygon, such as a waiting area, to measure currently tracked people whose footpoints are inside it. Save the configuration.
2. Switch to **Draw two-point counting line**. Click two line endpoints on the camera frame, name it, add it to the draft, then **Save configuration**. Direction is defined by the endpoints. Negative→positive side crossings count as entries and reverse crossings as exits; change the endpoint order to reverse the meaning.
3. Adjust **People-flow thresholds**. Dwell observations need sustained tracked membership; possible queues need multiple low-motion people sustained through the configured window.
4. Resume/restart the camera after any configuration edit. Observe **People flow · current session** in Overview and review observations under Events.

**Important:** a single YOLO count is people *visible in the image*. Zone occupancy counts tracked footpoints *inside an image polygon*. Entry/exit totals are crossings observed *in the current session*, not a reliable census of everyone inside a building. Counts reset on camera interruptions or source/configuration changes and may miss crossings under occlusion. At 2 FPS, rapid crossing and ID switches remain possible.

## Verify with real input

After starting the selected camera in RoadPulse:

```sh
make verify-people
```

This read-only acceptance probe checks that **two or more distinct processed frames** reach the local API while the real `person` detector is running, and reports whether at least one positive person detection occurred. It does **not** validate detection accuracy or tracking accuracy. It requires a running backend and an activated locally controlled live source. See [current architecture](docs/ARCHITECTURE.md), [FlowPulse acceptance and limitations](docs/FLOWPULSE_MIGRATION.md) and [controlled evaluation protocol](docs/FLOWPULSE_EVALUATION.md).

A meaningful portfolio evaluation also requires manually counted, consented trials: people crossing a line in both directions, two or three people dwelling in a zone, clearing the zone, and camera disconnect/reconnect. Report actual measured errors rather than estimated accuracy.

## Commands

| Command | Purpose |
| --- | --- |
| `make dev` | Start FastAPI and Vite on localhost |
| `make model` | Install optional Ultralytics and download YOLO11n (already done on your Mac) |
| `make lint` | Python + TypeScript/ESLint checks |
| `make test` | Backend and frontend test suite |
| `make build` | Frontend production build |
| `make verify-people` | Verify live person-processing status from a running, activated local camera |
| `make demo` | Explicitly launch the archived vehicle fixture for developer regression (not person analytics) |

## Legacy adapters and limitations

The prior RoadPulse traffic APIs, Fintraffic snapshot/TMS integration, and traffic event engine remain in the repository for compatibility and regression testing. Fintraffic snapshots are not continuous video and cannot drive crossing/dwell/queue rules. For FlowPulse presentations, choose an owned live camera; never present the generated traffic fixture as people-flow data. The Python `app` import namespace and `ROADPULSE_` environment prefix are deliberately retained to avoid an unnecessary rewrite.

This system does not identify people or infer demographics, intent, emotions, or medical characteristics. Temporary IDs may switch across occlusions; person detections can be missed or falsely triggered. Possible-queue alerts are **hypotheses**, not proof of queuing. No real-world accuracy percentage or production security guarantee is claimed. Keep the service on localhost and follow privacy law and participant consent.

Licensed AGPL-3.0-or-later; optional Ultralytics integration has its own AGPL/commercial terms. See [LICENSE](LICENSE) and [upstream Ultralytics licensing](https://www.ultralytics.com/license).

## Simple and Advanced people analytics

**Simple** (the default on the Live overview) immediately shows current person
 detections, temporary tracks, actual processed FPS and a bounded in-memory count
 trend after connecting a permitted local camera. No zone drawing is required.
 **Advanced** keeps directional line crossings, zone occupancy, dwell and possible
 queue observations. In **Zones & lines**, one-click presets can add a full-frame
 zone, a central waiting area or a starter entrance line; these are templates, not
 automatically recognized physical boundaries. See
 [Simple and Advanced modes](docs/SIMPLE_ADVANCED_MODES.md).

### Automatic analytics (no polygon setup)

A local camera now reports count trends, recent average/peak visible people, a coarse busiest image sector, and anonymous image-center left/right crossings without any zone configuration. These are **image-plane signals**, not physical entry/exit or queue measurements. Full-frame presets remain count-only to avoid spurious dwell/queue events. See [Automatic analytics](docs/AUTOMATIC_ANALYTICS.md) for privacy, validation, and limits. Camera consent remains explicit.

## Release and validation

The initial page load uses the FlowPulse privacy-first startup screen while the
local backend is contacted. It does not open the camera or simulate inference.
The regular workspace then uses a compact introduction to prioritize live data.

See [release acceptance and count evaluation](docs/RELEASE_CHECKLIST.md) for
real-camera checks and the local count-error evaluator (`backend/scripts/evaluate_counts.py`).
Neither automated tests nor the branded startup experience proves detection accuracy.


## Café Edition: simple owner workflow

The default dashboard is now organized into **Live café**, **Shift summary**, **Service alerts**, **Camera setup**, **System health**, and **About FlowPulse**. The main experience needs no manually drawn zones: after explicit camera permission and a preview, anonymous per-frame people counts and automatic session summaries begin on **Start monitoring**. Physical doorway counting and area-specific queue alerts still need a correctly confirmed geometry; the technical editor is hidden under optional expert tools. This prototype never claims precise customer visit duration, customer identity or certified wait time.

See [Café owner guide](docs/CAFE_OWNER_GUIDE.md) for setup, automatic metrics, limitations, and validation.

### Café owner service-alerts upgrade

The **Service alerts** page replaces the owner-facing manual observations inbox with
current on-screen condition signals. Desktop browser notifications are optional,
explicitly permissioned, and work only while the app is open. Historical records,
including old starter-template observations, remain available under **System health
→ Historical observation archive**. The default starter waiting-area template
no longer raises dwell/queue events until adjusted and renamed. The **Shift
summary** now offers minute-average CSV export and intra-session activity
comparisons. This does not produce certified customer counts, actual waiting
times or a cross-day learned baseline. See `docs/CAFE_AUTOMATIC_ALERTS.md`.

### Café guest-facing area estimate (optional)

The owner can optionally exclude one confirmed **staff-only half** of a fixed local camera image under **Camera setup**. FlowPulse reports **people in that guest-facing area** separately from the full visible-person count; it **does not identify staff or customers**. The setting is local and can be disabled, and changing it resets the current session summary. See [Café guest-area guide](docs/CAFE_GUEST_AREA_GUIDE.md) for limitations, notification behavior and acceptance tests.

### Automatic scene intelligence (no manual zones)

FlowPulse now discovers **recurring camera-view activity hotspots** from actual anonymous YOLO person detections and temporary motion estimates. It highlights frequent presence, longer stays and movement after the live camera has collected enough healthy frames. The map is available on **Live café** and **Camera setup**, and longer-stay hotspots are shown as informational suggestions, never as automatic queue or staffing judgments. No operator drawings, cloud uploads, face recognition, clothing classifiers or retained individual profiles are required. The optional staff-only area filter is preserved but hidden by default; it does not identify employees. See [automatic scene discovery guide](docs/CAFE_AUTOMATIC_SCENE_DISCOVERY.md) for limitations and a real-camera validation protocol.

### Café scene intelligence and local shift comparison

The main dashboard overlays anonymous activity hotspots on the current fixed camera frame and distinguishes **time sampled in an area** from **separate occupancy periods**. Neither is a count of unique visitors or detected staff. Persistent camera-view movement warnings prevent an unreliable session from being added to local shift history. Café owners do not need to upload video, mirror their phone display, configure OBS, or draw polygons to use basic scene insights.

**Shift summary → Local shift memory** is optional, off by default. It retains up to 30 days of aggregate counts; only stable sessions with at least 300 processed frames and four minutes of monitoring are eligible. Historical comparisons require three eligible saved sessions from the same camera ID and selected area, and use the median plus range of previously observed counts. They are not a verified business benchmark or calibration of the camera between days. Turning the option off erases stored summaries. See [scene and shift guide](docs/CAFE_SCENE_AND_SHIFT_GUIDE.md).

### Person-detection quality and stable boxes

The local café detector now uses higher-resolution adaptive YOLO11n person input, with short-lived corroboration for weaker candidates and a separately labeled, uncounted visual grace box after a missed sample. It does **not** recognize identities, occupations, or customer visits. See [Person detection quality](docs/CAFE_PERSON_DETECTION_QUALITY.md) for limitations and a practical accuracy check.

### Detection Quality & Trust (local evaluation)

The Live Café and Shift Summary now distinguish *sustained high visible counts* (a five-sample median requiring nearby observations) from a raw one-frame maximum, which remains available in technical diagnostics. Adaptive detail scanning records per-frame overlapping candidates suppressed. Sampled green boxes fade when their original AI frame becomes too old to represent the smoother video. Neither measure identifies people or guarantees detection through occlusion.

A local, optional comparison utility can evaluate different **already installed** YOLO weights against annotated people boxes or human-counted snapshots. It never uploads video or changes the active model by itself. See [Detection Quality & Trust](docs/CAFE_DETECTION_QUALITY_TRUST.md).

## Portfolio release and demonstration

FlowPulse is a **portfolio/research prototype**, not a field-validated or certified people counter. A replayed café video processed through OBS is **live AI inference on prerecorded footage**, not a live customer installation. Publish only footage and screenshots you have explicit rights to share. No results from a manually annotated field evaluation have been supplied with this repository.

Run `python3 scripts/release_prep.py` to check GitHub publication hygiene and locate old patch/backup files. Optionally run `python3 scripts/release_prep.py --quarantine` to *move* those leftovers into a timestamped folder in `~/Downloads` instead of deleting them. Run `make lint && make test && make build`, verify the real Mac camera lifecycle, and follow the [v1 release checklist](docs/RELEASE_CHECKLIST.md) and [GitHub publication guide](docs/GITHUB.md).

For a portfolio walkthrough use the [current café demo guide](docs/CAFE_DEMO.md). The older [vehicle demo guide](docs/DEMO.md) covers only the archived RoadPulse fixture.
