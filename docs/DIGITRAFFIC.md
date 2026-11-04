# Fintraffic Digitraffic: current snapshots and official TMS

RoadPulse supports a selected road-weather camera snapshot and a separately selected roadside TMS station. The existing synthetic demo and continuous-video pipeline remain available. No video collection or upload is required for this provider.

## Setup and first camera

The existing `.env` was backed up under ignored `runtime/config-backups/` before editing. Its missing replay path is cleared; generic camera permissions remain false. These fields enable the scoped official provider:

```dotenv
ROADPULSE_CAMERA_MODE=replay
ROADPULSE_REPLAY_PATH=
ROADPULSE_MODEL_PATH=runtime/models/yolo11n.pt
ROADPULSE_DEVICE=cpu
ROADPULSE_DIGITRAFFIC_ENABLED=true
ROADPULSE_DIGITRAFFIC_USER=RoadPulse-AI/local-research
ROADPULSE_CAMERA_ANALYSIS_AUTHORIZED=false
ROADPULSE_CAMERA_REDISPLAY_AUTHORIZED=false
ROADPULSE_SAVE_EVIDENCE=false
```

Do not put a Digitraffic JPEG or metadata API into `ROADPULSE_CAMERA_URL`. The dedicated adapter resolves the selected image URL from official preset metadata. The general-purpose authorization flags apply to unrelated configured sources, not this documented CC BY 4.0 integration. The app stays bound to localhost.

From the repository root:

```sh
make model                 # only if dependencies/weights are not already installed
make verify-model          # real weights on generated pixels; execution only
make verify-digitraffic    # small real API/JPEG/YOLO probe; no image history saved
make dev
```

Open http://127.0.0.1:5173. On Overview or Camera & Zones:

1. Choose **Source type → Public Road Cameras** and search a real station by name/ID.
2. Select a station; RoadPulse requests its detailed metadata and lists presets reported in collection. Choose any currently available station/preset. The verifier now discovers bounded alternatives automatically; the documentation example C1451601 is not a mandatory default.
3. Click an available preset. Only the selected preset image is fetched and processed by local YOLO. No directory thumbnails or bulk camera inference run.
4. Confirm **CURRENT CAMERA SNAPSHOT**, camera/preset ID, name/location, image time/type, age, next-refresh estimate, detector and vehicle count. Zero is a valid detection count.
5. Inspect boxes and confidence labels on the selected JPEG. These overlays modify the original image and are attributed accordingly.
6. Choose **Source type → Demo → Start Demo** to return to the original demo. A separately configured video source remains in this selector too.

An image-time label may say **provider measuredTime** or **HTTP Last-Modified**. The latter is an image-update time, not guaranteed exposure time. Request/receipt time is separate. Unknown or over-30-minute provider timestamps produce STALE; cached/unchanged images never get a fresh capture timestamp. A refresh estimate is not a provider guarantee.

## Official endpoints and policy

The [road-traffic documentation](https://www.digitraffic.fi/en/road-traffic/) lists the supported APIs. See [Swagger](https://tie.digitraffic.fi/swagger/) for the full current contract. The adapter uses:

- `GET https://tie.digitraffic.fi/api/weathercam/v1/stations` — camera GeoJSON directory.
- `GET https://tie.digitraffic.fi/api/weathercam/v1/stations/{id}` — station/preset metadata and image URLs.
- `GET https://tie.digitraffic.fi/api/weathercam/v1/stations/{id}/data` — selected preset measurement time.
- `https://weathercam.digitraffic.fi/C1451601.jpg` — documented example JPEG; production selection uses the metadata URL.
- `GET https://tie.digitraffic.fi/api/tms/v1/stations` — independent TMS station directory.
- `GET https://tie.digitraffic.fi/api/tms/v1/sensors` — provider sensor definitions.
- `GET https://tie.digitraffic.fi/api/tms/v1/stations/data` — current computational sensor values.

Fintraffic permits reuse under [its CC BY 4.0 terms](https://www.digitraffic.fi/en/terms-of-service/). The UI credits **Fintraffic / digitraffic.fi**, links [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), and identifies RoadPulse's added overlays. Availability, timeliness and accuracy are not guaranteed; there is no implication of Fintraffic endorsement. No registration, paid inference or API key is used by this adapter.

[Usage instructions](https://www.digitraffic.fi/en/support/instructions/) require compressed API responses and recommend an application-identifying `Digitraffic-User` header. Do not include personal details in that header. RoadPulse sends gzip support, pools HTTP connections, uses conditional validators, and requests only vetted HTTPS paths on the two official hosts. Redirects are rejected rather than followed to an unvetted destination.

## Cadence and retention

Fintraffic documents camera updates at approximately ten-minute intervals. RoadPulse caches images for ten minutes, camera/TMS directories and sensor definitions for six hours, selected-camera metadata for ten minutes and TMS measurements for one minute. It has a shared request-rate cap, bounded in-memory LRU/byte limits, 5-second connect/read timeouts, a response time budget, decompressed payload limits and capped error backoff. HTTP 429 honors Retry-After (seconds or HTTP date) across the client; other errors back off. A 304 reuses existing bytes without a new inference. Identical JPEG bodies with different validators are also deduplicated.

Snapshot confidence is configurable through Camera & Zones; changes apply to the next changed provider image. Refreshing the UI does not force repeated inference.

Only one selected source feeds the existing bounded frame queue and inference worker. The loaded YOLO instance is reused across real-source switches. Raw images are memory-only; the integration probe writes a JSON report, not camera images. Optional event evidence remains source-pixel-free schematics, and snapshot sources cannot create temporal events.

## Snapshot limitations

Snapshots have no cross-image vehicle identity, motion speed, stopped-vehicle events or validated congestion severity. YOLO counts are visible objects in one image, not official traffic volume. Night, snow, shadows, occlusion, perspective and distant objects can cause missed or incorrect detections. No real-road accuracy has been measured in this session.

Continuous-video tracking and temporal rules remain implemented for separately authorized sufficiently frequent streams. New configured cameras start without monitoring zones. The tracker is RoadPulse's lightweight anonymous association baseline, not ByteTrack.

## Separate official TMS data

Use **Browse TMS stations** and manually select an official roadside measurement station. Its name and coordinates are displayed, with an explicit statement that it is not automatically matched to the camera. RoadPulse does not assign measurements by proximity.

The TMS panel shows available nonnegative numeric speed/count values with original units, sensor name, direction/window identifiers where supplied in the name, measurement timestamp and stale flag. `km/h` is speed; `kpl` is the provider's count notation. Aggregation windows remain tied to the sensor definition/name; RoadPulse does not infer a camera's volume from a sensor nearby. Missing, invalid, unrecognized-unit or disconnected-station values produce an empty state. Measurements older than five minutes are labeled stale. No placeholder charts are inserted.

For a deliberately selected TMS ID, run:

```sh
.venv/bin/python backend/scripts/verify_digitraffic.py --station C14516 --preset C1451601 --tms YOUR_NUMERIC_TMS_STATION_ID
```

Do not include `--tms` unless you have selected an actual station from the directory.

## Troubleshooting and acceptance

- **403:** review provider access/service instructions and network policy; no bypass or substitute feed is attempted.
- **404:** station/preset may be removed or unavailable. Reload the directory and choose another reported preset.
- **429:** wait for Retry-After/backoff. Repeated UI refreshes reuse backend cache and do not force image requests.
- **5xx/network/TLS:** diagnostics report the provider failure. Previously processed content is not relabeled as newly captured; synthetic demo is available only by explicit selection.
- **STALE/unknown timestamp:** inspect image time, timestamp type and provider status; unchanged pixels are not proof of new data.
- **No presets:** station state/collection flags may disallow use. No fake presets are inserted.
- **YOLO unavailable:** check the local weights path and `make verify-model`; model failures are separate from provider failures.
- **Unsupported response schema:** the provider contract could not be checked against live responses from this restricted session. Mock contracts are tested, but the real probe is the required compatibility gate. Preserve its JSON report and compare the current official Swagger/response if parsing fails.

Actual acceptance requires the real probe and browser workflow on the user's Mac. The user's curl verified HTTP 200 metadata and a JPEG download, not RoadPulse inference. This session's external DNS and localhost restrictions prevented a successful end-to-end real-provider demonstration. See [verification](VERIFICATION.md).

## Updated source and visual acceptance

The explorer is a compact source-control workflow with opt-in thumbnails, source-specific errors and an explicit demo switch. Snapshot image facts and attribution sit beside the actual frame; TMS is a separate measurement card. Snapshot Camera & Zones uses the same selected image with confidence settings, and Events defaults to the current camera. The old demo is cleared before attempting a real-source activation, including failure paths. Image endpoints reject mismatched camera/frame IDs.

See [the exact real-network Mac acceptance procedure](MAC_ACCEPTANCE.md). It includes `make verify-positive`, `make verify-tms` and `ROADPULSE_REAL_E2E=1 make e2e`. Do not report a genuine end-to-end success or positive traffic detection until the corresponding real checks pass. A direct JPEG HTTP 200 alone does not prove current metadata availability.

## Missing state and alternative selection repair

The reported C01504 failure was caused by requiring `state == "OK"`. The
operator saw a missing/null state with collectionStatus GATHERING and three
in-collection presets. That proves a filter rejection, not camera inactivity.
This agent could not fetch the actual C01504 JSON or full Swagger schema; it
does not assert that a missing state is healthy or that a field was renamed.

Missing state now stays unknown. Detailed collectionStatus must be GATHERING,
inCollection must be a true boolean, explicit fault states remain excluded,
and actual official JPEG decoding plus valid freshness are required before
any pixels are yielded for inference. Unknown/missing time and images older
than 30 minutes fail clearly. Simplified directory omissions trigger detailed
checks rather than a false availability claim. No None-to-OK coercion occurs.

Use **Find verified fresh alternatives** when a station fails. At most six
station details and three images are checked, up to two checked alternatives
are offered, and selection is explicit. Results are cached; no all-camera
thumbnail/inference sweep runs. Verification refers to JPEG decoding/time as
of the check, not detector accuracy or guaranteed future availability.

```sh
.venv/bin/python backend/scripts/verify_digitraffic.py --station C01504 --seek-positive
```

The station is a preference with bounded fallback, not a mandatory active
preset. Preserve runtime/digitraffic-positive-verification.json and its actual
station metadata checks/types. A real API/JPEG/YOLO/browser pass is still required
on the network-enabled Mac; mocked tests do not establish it.
