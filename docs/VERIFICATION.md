# Verification — lifecycle, source clarity and road acceptance

## Established baseline and remaining acceptance

The user reports successful actual Mac webcam imagery with local YOLO at about
2 FPS indoors. Zero vehicles/tracks/observations were expected. This is useful
real capture/model/browser evidence reported by the operator, not positive road
vehicle detection or a new independent hardware test by this agent.

**The full road-traffic system is not verified.** Actual moving road vehicles,
real tracking quality and traffic-event accuracy remain unverified. This agent's
native camera probe was denied by macOS, public provider requests were blocked,
and browser server startup could not bind localhost. No screenshots were produced.

## Repairs implemented in the existing app

- Explicit Start, Pause, Resume, Stop camera and Switch source controls. Pause
  releases capture/worker resources but retains one labeled still; it reports
  PAUSED and zero FPS, not OFFLINE. Resume reopens the same source with fresh IDs
  and temporal baselines. Stop clears delivered image/ID and waits for release.
- Local capture normally executes VideoCapture.release in its child finally;
  bounded terminate/kill is the fallback for blocked native capture. If a process
  cannot be reaped, release is not acknowledged and the backend stays STOPPING.
  Switching sources waits for prior capture release before opening another.
- Lifecycle status is separate from input mode. mode=LIVE describes configured
  input; PAUSED/OFFLINE/STOPPING are states. Model errors cannot claim OFFLINE
  while capture remains open. Backend unreachability is not a camera-release
  acknowledgement. Control revisions reject delayed pre-stop WebSocket/REST state.
- One Source type selector: My Live Camera; Public Road Cameras (Fintraffic
  snapshots); External Live Road Stream (only configured/authorized); Demo.
  Configured replay/other snapshot inputs remain available when configured.
  Active-source display is read-only; mobile Stop controls are no longer hidden.
- Owned device index selection and optional system listing, real selected-device
  preview, then explicit Start road monitoring. Preview runs actual YOLO through
  the existing pipeline but suppresses temporal observations even with saved
  zones. No all-camera capture sweep occurs. Continuous-video verification needs
  two different received frames and resets on each connection.
- Existing model, tracker, SQLite, zones, event rules and generated demo are
  preserved. Valid monitoring zones are required for observations. No vehicle
  detections means no vehicle observations, including in a monitored indoor scene.
  The tracker remains the spatial/velocity association baseline, not ByteTrack.
- Added strict make verify-road acceptance: real live source/model/JPEG identity,
  positive vehicles plus a repeated track with image-plane motion, and a live
  source at probe end. This is not proof of road context or labeled accuracy.
  Basic verify-live does not imply positive vehicle or road-event acceptance.

## C01504: cause, conditional fix and limits

The old adapter required state == "OK". The operator's reported missing/null state
therefore caused rejection despite collectionStatus=GATHERING and inCollection
3/3. That confirms a filter rejection; it does not establish the provider's reason
for omitting state or prove image availability.

Official documentation names state, collectionStatus and inCollection and
separates simplified directory from detailed metadata. Actual C01504 JSON/full
Swagger could not be retrieved here (curl DNS failure, research tool cache/access
failure); repository inspection did not reveal a usable field definition. No
renamed field, deprecated field or healthy state is invented.

The repair uses tri-state evidence. Simplified omissions trigger detail checks.
Detailed collectionStatus must be GATHERING, inCollection remains strict boolean
true, and explicit non-OK/fault metadata is rejected. Missing state stays UNKNOWN,
not OK: only an official-host/path JPEG that decodes with valid fresh provider or
explicitly labeled HTTP-update time can yield pixels. Missing/old timestamps fail.
The same gate is used by production capture and the dynamic verifier.

Find verified fresh alternatives is explicit, bounded (six station details/three
images, up to two suggestions), cached and never automatically activates a new
camera. The suggestions establish image decoding/freshness as of their check,
not detector accuracy or permanent station health. Actual Fintraffic JPEG → YOLO
→ browser acceptance remains pending on the network-enabled Mac.

## Actual checks executed

| Check | Actual result |
| --- | --- |
| make lint | PASS: Ruff/format (43 files), mypy 3.12 (17 app files), ESLint, TypeScript |
| make test | PASS: 92 backend tests; 20 frontend tests in five files |
| Focused local-camera/provider regressions | PASS: 44 tests |
| make build | PASS: production TypeScript/Vite build |
| make benchmark | PASS: generated 160-frame scenario emits both expected rule types; not real traffic/model performance |
| make verify-model | PASS: actual Ultralytics 8.4.195 / yolo11n.pt, CPU; five generated frames, counts [0,0,0,0,0] |
| make verify-digitraffic | FAIL at directory fetch: network/TLS error; no official image obtained |
| Actual C01504 curl | FAIL: Could not resolve host tie.digitraffic.fi |
| verify_live.py --local --authorize-owned-camera --seconds 5 | FAIL: macOS denied AVFoundation camera access; model loaded, zero real frames, 0 FPS |
| make verify-road | FAIL before source testing: local backend inaccessible in this execution environment |
| make e2e | Attempted; Uvicorn could not bind 127.0.0.1:8000 (EPERM), so browser tests did not execute |

One upstream Starlette/httpx deprecation warning remains visible. No lint/type
checks were suppressed. Latest generated-image warm inference calls were about
39–43 ms, not measured road throughput. Native capture/stream FPS cannot be
inferred from those timings. Current ignored reports include model-smoke-cpu.json,
digitraffic-verification.json, live-verification.json and road-verification.json
under runtime. The previous record is preserved as
runtime/verification-before-lifecycle-repair.md.

## What the tests establish

Lifecycle regression uses mocked devices/detector with actual API and worker
threads: preview is event-suppressed; saved zones do not activate preview events;
start/pause/release/resume/new IDs/switch/release/stop/clear occur in order; FPS
is immediately zero; paused frames remain labeled PAUSED after normal stale
limits; failed close never reports release/OFFLINE. A child-worker test checks
release, and a separate native decoder test uses generated video, not a webcam.

Provider mocks cover absent/null/OK/fault/wrong-type state, incomplete summaries,
strict collection gating, actual JPEG decoding and exact decoded pixels sent to
inference, freshness, unchanged-image deduplication, cached bounded alternatives,
HTTP failures and timestamps. No mock road-camera catalog is added to production.

React tests cover the one selector, explicit preview consent/index, replacement
of demo image, source-specific pages/events, zero detections, image retry,
Pause/Resume/Stop controls and delayed-status rejection. The genuine browser
acceptance test was updated for preview → monitoring → mobile Stop → pause and
release → resume → stop and clear → Demo. It was not executed successfully here.
A mocked browser test is never counted as real vehicle tracking evidence.

## Independent real-world milestones

| Milestone | Evidence |
| --- | --- |
| Model loads/executes | PASS: independent real-weight generated-image smoke |
| Real webcam image inference | USER-REPORTED PASS indoors; not independently repeated here |
| Actual webcam browser display | USER-REPORTED PASS indoors; latest browser gate blocked here |
| Physical hardware release after new Stop | NOT VERIFIED on hardware; automated release/ordering tests pass |
| Selectable Continuity Camera | Implemented when exposed by macOS; hardware selection NOT VERIFIED here |
| Positive road vehicle detection | NOT VERIFIED |
| Repeated real-road moving vehicle tracks | NOT VERIFIED |
| Real stopped/congestion observations | NOT VERIFIED; timing/zone/reset tests pass on generated/mocked evidence |
| Real-world traffic-event accuracy | NOT VERIFIED; no labeled road evaluation |
| Actual Fintraffic image selection/inference/browser | NOT VERIFIED after this repair; conditional gate tested with mocks |
| Authorized public continuous road stream | None verified/enabled |

## External sources and handoff

Official Iowa feed/terms pages were revisited. They document keyless GIS discovery
and separate XML access, but site terms restrict automated content monitoring;
footage analysis/redisplay rights were not established. Caltrans has documented
free CCTV data and previously observed official streamingVideoURL HLS candidates;
current directory/playlist fetches and actual decoding/FPS remain unverified.
Metadata licensing is not extended to footage. Neither provider is silently enabled.
See [CONTINUOUS_SOURCES.md](CONTINUOUS_SOURCES.md) for primary sources and limits.

Follow [MAC_ACCEPTANCE.md](MAC_ACCEPTANCE.md) for device preview, safe stationary
road view, valid zones, strict vehicle acceptance, hardware-release checks and
Fintraffic diagnostics. No .env mutation was necessary; it remains ignored, with
the replay path empty and installed model path preserved. No new paid dependency,
cloud inference, camera image history, private URL or credential was introduced.

Changed files: pipeline.py, local_camera.py, digitraffic.py, main.py;
verify_live.py, verify_digitraffic.py; local/provider/rule tests;
App.tsx, useLive.ts, DigitrafficPanel.tsx, types.ts, style.css;
frontend status/connection/dashboard/provider tests and source/live browser tests;
Makefile, .env.example, README and source/architecture/acceptance/verification docs.

## FlowPulse person-analytics migration — November 2, 2026

This section describes the separate people-flow implementation added to RoadPulse's existing camera/YOLO/React/FastAPI/SQLite infrastructure. It does not reclassify old road-event results as person analytics.

- Local YOLO now supports person class 0; person is the default detection target on real inputs. Existing demo remains vehicle-only.
- A new flow rule engine implements polygon occupancy, oriented line crossings with hysteresis/cooldown, zone dwell and a sustained low-motion group queue heuristic.
- Snapshot-only and preview-only inputs cannot generate temporal people-flow events. Stop/disconnect resets session counters.
- Real person detections, crossing precision/recall, ID stability, iPhone capture and UI behavior require acceptance testing on the user's Mac.
- See `docs/FLOWPULSE_MIGRATION.md` and `docs/FLOWPULSE_EVALUATION.md` for required Mac and controlled-validation procedures.
