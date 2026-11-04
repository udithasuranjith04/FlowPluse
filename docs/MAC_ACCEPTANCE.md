> **Historical RoadPulse road-camera guide.** Current café instructions are in [the owner guide](CAFE_OWNER_GUIDE.md) and [the release checklist](RELEASE_CHECKLIST.md).

# Road-monitoring acceptance on the Mac

The user has verified real Mac webcam imagery with local YOLO at about 2 FPS
indoors. Zero vehicles and observations were expected there. **Moving-road vehicle
detection/tracking and traffic-event accuracy are not yet verified.** This agent's
own camera access and localhost browser servers remain blocked; mocks are not
real-road acceptance.

## Restart and choose one source

Stop old `make dev` processes first: the backend does not hot-reload Python edits.

```sh
cd /path/to/your/FlowPulse
make lint
make test
make build
make verify-model
make dev
```

Open http://127.0.0.1:5173. Use the single **Source type** selector:

| Choice | Evidence and capabilities |
| --- | --- |
| My Live Camera | A camera you control; continuous-video input, local YOLO, anonymous tracking; observations require monitoring zones |
| Public Road Cameras | Fintraffic current snapshots at approximately ten-minute intervals; per-image YOLO/counts; no tracking or temporal observations |
| External Live Road Stream | A separately authorized direct video source configured on the backend; unavailable when none is configured |
| Demo | Generated footage and fixture color detector; demo events remain separate |

Configured permitted file replay/other snapshot input remains available as an
additional option only when configured. The active-source name is read-only;
**Switch source** returns focus to the one selector. Choosing a category does not
silently activate it. A failed real source never becomes generated footage.

## Owned camera: preview, confirm, monitor

1. Choose **My Live Camera**. Select a device index (0–15). Start with the index
   you already verified, or click **List system cameras** and select an exposed
   camera. Listing uses optional FFmpeg without opening all capture streams;
   when unavailable, the app says so and permits a manual index.
2. Confirm you control the selected camera and permit local processing/display.
   Click **Preview selected camera**. Only this device is opened. A previous
   source is closed before another device is opened.
3. Preview uses actual camera pixels and YOLO, with temporal observations
   disabled even if old zones exist. Require a real photograph with the selected
   device's view. The app waits for two different frames before claiming
   verified continuous video. Zero vehicle boxes in an indoor scene is valid.
4. Aim a stationary, safely mounted camera you control at normal moving traffic
   from a safe authorized location. Do not operate the dashboard while driving
   or stage road hazards. Check that vehicles occupy enough pixels to be useful;
   nighttime/distant/occluded traffic can be missed. Do not move the camera to
   manufacture vehicle-motion evidence.
5. Click **Start road monitoring** to explicitly confirm the intended view.
   The source restarts with a fresh tracking session. Require Ultralytics /
   yolo11n.pt, CPU, fresh frame identity, actual measured source/processed FPS,
   genuine vehicle boxes/classes/confidences and anonymous IDs where detected.
6. Click **Pause** before drawing zones. On Camera & Zones, draw monitoring and
   ignore polygons on the labeled paused image and save configuration. No
   monitoring zone means no stopped-vehicle/congestion observations. Inspect
   existing zones when a device index changes: macOS may reorder devices.
7. Click **Resume**. It reopens capture and starts fresh IDs/baselines. Check
   actual cars/buses/trucks/motorcycles across successive frames; matching IDs
   should persist sensibly. The tracker is the existing spatial/velocity baseline,
   not ByteTrack. Review IDs through occlusion/crossing rather than asserting
   accuracy from a few examples.
8. Detection sampling defaults to 2 FPS. Change **Detection sampling** in Camera
   & Zones for this source; `ROADPULSE_TARGET_FPS=2` sets the default for new
   configurations. Saved per-source settings take precedence. Superseded frames
   are expected when capture is faster than inference; the latest-frame queue
   prevents backlog. Diagnose freshness and latency as well as FPS.
9. Navigate Overview, Camera & Zones, Diagnostics and Events, then refresh the
   browser. The backend's selected source persists while it runs. Events default
   to this source; demo history must not appear as new real-camera incidents.

A Mac webcam and an iPhone Continuity Camera use the same selectable AVFoundation
adapter when macOS exposes them. RoadPulse cannot guarantee OS device exposure.
For compatible devices and setup, use [Apple's official Continuity Camera guide](https://support.apple.com/en-gb/102546).
Allow the launching Terminal/app in macOS Privacy & Security → Camera; close other
camera apps before testing. Optional device listing does not grant camera access.
No API key, video upload or `.env` edit is required for session consent.

## Lifecycle acceptance: confirm hardware release

| Control | Expected behavior |
| --- | --- |
| Start camera | Opens the selected, already authorized source; an unconfirmed preview remains a preview |
| Pause | Intentionally stops workers and releases capture; PAUSED, zero FPS/tracks, retained last processed still clearly labeled |
| Resume | Opens the same source, resets tracker session/temporal baselines; verify new changing frames |
| Stop camera | Waits for capture close/process termination, clears delivered image/ID, reports OFFLINE and device_released=true |
| Switch source | Offers the single selector; activating another source closes the prior capture first |

With other camera apps closed, click **Stop camera** and confirm the webcam
indicator turns off (allow for the OS indicator updating). Diagnostics must show
capture released, no workers delivering frames and zero FPS. The JSON check is:

```sh
curl --fail --silent http://127.0.0.1:8000/api/system/status | \
  .venv/bin/python -m json.tool
```

Require `state: OFFLINE`, `device_released: true`, `frame_id: null` and zero
capture/processing FPS. Reopen the device to confirm it is available, then Stop
again. Pause also closes the device for privacy but keeps a labeled still;
it is not a hidden live capture. If release cannot be confirmed the backend
stays STOPPING and reports an error; stop the backend before reopening. If
another app owns the camera, its indicator may remain on independently.

## Actual continuous and vehicle probes

While `make dev` is running and a selected real camera is actively monitoring:

```sh
# Second terminal, repository root:
make verify-live
make verify-road
```

`verify-live` refuses demo/replay/snapshot input and requires multiple different
processed frames, actual Ultralytics, JPEG/status identity agreement and a live
source at the end of the probe. It reports independent milestones rather than
claiming the whole road system passed. Inspect `runtime/live-verification.json`.

`verify-road` samples 30 seconds, additionally requiring positive vehicle
outputs plus a track ID seen in multiple frames with image-plane movement
above 0.001 image diagonals/second. Inspect `runtime/road-verification.json`.
That threshold is not real-world speed. The operator must verify the scene is
actually a stationary camera viewing moving road vehicles: the command cannot
prove road context or track correctness without labeled evidence. It should
fail indoors with zero vehicles. For sparse traffic, run a longer bounded check:

```sh
.venv/bin/python backend/scripts/verify_live.py --require-vehicles --seconds 60
```

For a standalone camera/pipeline probe, stop the app first to free the device:

```sh
.venv/bin/python backend/scripts/verify_live.py \
  --local --authorize-owned-camera --device-index 0 --seconds 15
```

This opens actual hardware with temporary SQLite and recording off, and saves
only metadata in the report. It does not validate browser rendering. A model
execution pass on generated geometry (`make verify-model`) is a separate check.

Temporal observations require sufficient track age, stationary duration or a
valid moving baseline and sustained queue evidence in valid monitoring zones.
Passing traffic alone does not validate either event rule. Do not stage a hazard;
real-event accuracy remains unverified until evaluated on appropriate authorized,
labeled traffic evidence. Observations always require human review and do not
prove crashes, violations, absolute speed or official traffic volume.

## Genuine browser gate

Stop old servers before the automated test, and grant the launching Python/app
camera permission. No model/source/image mocks are used in this opt-in test:

```sh
ROADPULSE_LIVE_E2E=1 make e2e
# If an actual different device index is exposed:
ROADPULSE_LOCAL_CAMERA_INDEX=1 ROADPULSE_LIVE_E2E=1 make e2e
```

The test uses preview → explicit monitoring, requires changing rendered frames
and actual Ultralytics, checks Camera & Zones and mobile Stop visibility, then
pause/release, resume, stop/clear and return to Demo. It is not a positive vehicle
or road-event accuracy test. Camera screenshots are off by default; explicitly
add `ROADPULSE_E2E_SCREENSHOTS=1` to save one to ignored runtime.

The repeatable UI source-switch test is separately mocked:

```sh
cd frontend
npm run test:e2e:ui -- --grep 'mock source selection'
```

## Public Road Cameras: Fintraffic snapshot acceptance

With installed weights and the existing provider enabled, no private URL or key
is needed. Source type → Public Road Cameras → search/select station → choose
an orientation → **View this real camera**. Require the actual road JPEG,
CURRENT CAMERA SNAPSHOT, actual model/counts/boxes and provider time/age/type.
Never expect continuous motion or cross-image IDs from ten-minute snapshots.

C01504 was rejected by the old strict state==OK gate. Missing state now remains
unknown: detailed collectionStatus must be GATHERING, presets must be true
inCollection booleans, explicit fault states remain rejected, and a valid fresh
JPEG/timestamp must pass before yielding pixels. This agent could not retrieve
the live C01504 JSON/full schema; no healthy state, renamed field or successful
real connection is asserted. On failure, click **Find verified fresh alternatives**;
only a bounded subset is checked and no camera is automatically substituted.

```sh
make verify-digitraffic
.venv/bin/python backend/scripts/verify_digitraffic.py --station C01504 --seek-positive
```

The station is a preference, with bounded fallback, not a mandatory hardcoded
preset. Inspect the report's selected station/preset, official URL, source JPEG
hash, inference-frame hash, metadata field types, image timestamp and detections.
A successful inference with zero vehicles is not positive vehicle validation.
If parsing still fails, collect public diagnostics without credentials:

```sh
curl --fail --compressed --connect-timeout 5 --max-time 15 \
  -H 'Digitraffic-User: RoadPulse-AI/local-diagnostic' \
  https://tie.digitraffic.fi/api/weathercam/v1/stations/C01504
```

For genuine snapshot browser acceptance (stop old servers first):

```sh
ROADPULSE_REAL_E2E=1 make e2e
```

Compare the selected source/image IDs and original JPEG hash; check reload,
Camera & Zones, Diagnostics and source-filtered Events. Attribution must remain
visible. TMS measurements have their own selected sensor and are not YOLO counts.
Return using Source type → Demo → Start Demo. Third-party continuous road video
remains unavailable until actual transport and footage rights are verified; see
[CONTINUOUS_SOURCES.md](CONTINUOUS_SOURCES.md) and [VERIFICATION.md](VERIFICATION.md).
