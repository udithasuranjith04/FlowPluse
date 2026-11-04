# Continuous video candidates and controlled-camera setup

Reviewed 2026-11-01. **No external continuous source is verified and enabled.**
Metadata discovery, video decoding, permission for automated analysis and
dashboard display are separate checks. A public URL or GIS license does not
establish all four. No source permission flag was enabled by this investigation.

## Iowa DOT

- [Official 511 data feeds](https://iowadot.gov/travel-tools/iowa-511/511-data-feeds): GIS services need no credentials; XML feeds use a vendor request form.
- [May 28, 2026 migration notice](https://iowadot.gov/news/2026-05-28/media-advisory-iowa-dot-updates-traffic-camera-video-system-data-feed-usersdevelopers): image/video URLs changed and domain changes were expected. Discover current URLs, never reconstruct old streams.
- [Current ArcGIS layer schema](https://services.arcgis.com/8lRhdTsQyJpO52F1/arcgis/rest/services/Traffic_Cameras_View/FeatureServer/0?f=pjson) was readable through the research browser: `device_id`, `Desc_`, `ImageURL`, `VideoURL` are actual fields. Layer metadata is not a tested video feed.
- [DOT Terms of Use](https://iowadot.gov/policies-statements/terms-use) restrict automated monitoring/copying of site content and distinguish permitted browsing from other reuse. The GIS section now describes CC0 defaults with dataset exceptions; do not override a dataset's specific license or extend GIS terms to footage.
- [511 Data Feed Terms](https://iowadot.gov/policies-statements/511-data-feed-terms-conditions) describe feed disclaimers, termination and adjustable request limits. They were reviewed separately from GIS licensing. Applicability/permission for the intended automated footage use is not established here.

The layer query was attempted for only three populated video records; the
research browser could not fetch it and local curl failed DNS resolution. No
current Iowa video URL was obtained, opened or decoded. FPS, dimensions,
changing frames, authentication, session limits and geoblocking are **NOT
VERIFIED**, not inferred from the existence of `VideoURL`.

Metadata-only diagnostic on the Mac (does not authorize video analysis):

```sh
curl --fail --compressed --connect-timeout 5 --max-time 15 \
  'https://services.arcgis.com/8lRhdTsQyJpO52F1/arcgis/rest/services/Traffic_Cameras_View/FeatureServer/0/query?where=VideoURL%20IS%20NOT%20NULL&outFields=device_id,Desc_,VideoURL,ImageURL&resultRecordCount=3&returnGeometry=false&f=json'
```

For clarification, use the contact on the official migration/data-feed pages.
Ask whether one local research client may continuously decode a camera, run
YOLO, redisplay annotated frames locally and retain only anonymous observations;
request applicable attribution, polling/session limits and a statement covering
footage rather than just directory metadata. No email was sent by this agent.

## Caltrans CWWP2

[Official portal](https://dot.ca.gov/programs/traffic-operations/traveler-information/cwwp)
links to the [CCTV dataset documentation](https://cwwp2.dot.ca.gov/closed-circuit-television-cameras.html).
It offers free JSON/CSV/XML/TXT district data and prohibits usage that degrades
stream availability. No numeric streaming rate limit was established.

The actual [District 1 JSON](https://cwwp2.dot.ca.gov/data/d1/cctv/cctvStatusD01.json)
was readable in the research browser. Its structure is `data[] → cctv →
imageData`, with `streamingVideoURL` and separate `static.currentImageURL`.
For example a populated record supplied
`https://wzmedia.dot.ca.gov/D1/eureka_5th_r_320x240.stream/playlist.m3u8`.
This is a discovered **candidate HLS URL**, not a verified working/approved feed.
The playlist fetch was attempted once: unavailable through the research browser,
and local curl failed DNS resolution. Delivered FPS, resolution, duration,
changing frames and geographic availability remain **NOT VERIFIED**. A resolution
in the URL is not a measurement.

[Conditions of Use](https://dot.ca.gov/conditions-of-use) generally describe
public-domain information but warn that photographs/third-party content can
require further permission. Intended automated footage analysis and annotated
redisplay were not established for the selected camera. Leave disabled; consult
the official traveler-information coordinator if needed. Do not turn metadata
access into a claim of a tested stream or blanket footage authorization.

## Minnesota 511

The [official viewer](https://511mn.org/) returned no readable documentation in
the research browser. No documented direct-video API, access contract or analysis
grant was verified. No undocumented playback calls or token bypasses were used.
Status: **UNVERIFIED / NOT ENABLED**.

## Owned Mac camera: implemented alternative

Use Overview → Source type → My Live Camera. The app opens a camera only after explicit
operator confirmation (or a private persistent `.env` opt-in). Device discovery
uses optional FFmpeg AVFoundation listing with an eight-second timeout and
filters audio/screens; when unavailable it reports that limitation rather than
inventing device names. Device 0 is a manual index to try, not a proven inventory.
Continuity Camera must be exposed by macOS; indexes can change. Verify the view
before reusing saved zones.

Native capture runs in a spawned process with a one-frame queue, an eight-second
parent read limit, and bounded terminate/kill cleanup. It opens OpenCV
AVFoundation on macOS, resizes to at most 1280 pixels wide, records local receipt
time (not sensor capture time), and counts skipped sequences. Main capture and
inference retain the existing one-frame queue. Recording stays off by default.
Only the pretrained vehicle label set is used; no indoor object detection or
traffic accuracy is implied by a camera opening.

This environment actually attempted device 0; AVFoundation denied camera access.
No real frames, positive vehicles or browser video were verified. Grant access to
the launching Terminal/app in macOS Privacy & Security → Camera and follow
[MAC_ACCEPTANCE.md](MAC_ACCEPTANCE.md). Do not reset privacy permissions automatically.

## An owned local IP camera / authorized external video

Keep credentials and URLs in ignored `.env`. The following example is ONLY for
an IP camera you own/control, using the existing configured source:

```dotenv
ROADPULSE_CAMERA_MODE=live
ROADPULSE_REPLAY_PATH=
ROADPULSE_CAMERA_ID=owned-road-camera
ROADPULSE_CAMERA_NAME=My owned camera
ROADPULSE_CAMERA_PROVIDER=Camera owner
ROADPULSE_CAMERA_REGION=My location
ROADPULSE_CAMERA_URL=<actual direct HTTP(S), MJPEG, HLS or RTSP(S) URL>
ROADPULSE_CAMERA_ALLOWED_HOSTS=<exact source hostname>
ROADPULSE_CAMERA_ALLOW_PRIVATE=true
ROADPULSE_CAMERA_OWNED=true
ROADPULSE_CAMERA_ANALYSIS_AUTHORIZED=true
ROADPULSE_CAMERA_REDISPLAY_AUTHORIZED=true
ROADPULSE_CAMERA_PERMISSION_NOTES=<actual ownership/permission evidence>
ROADPULSE_CAMERA_PERMISSION_CHECKED=<actual YYYY-MM-DD>
ROADPULSE_CAMERA_SOURCE_PAGE=
ROADPULSE_CAMERA_TERMS_URL=
ROADPULSE_MODEL_PATH=runtime/models/yolo11n.pt
ROADPULSE_DEVICE=cpu
```

For a separately authorized public stream, set `ROADPULSE_CAMERA_OWNED=false`,
set `ROADPULSE_CAMERA_ALLOW_PRIVATE=false`, and provide the actual official
source-page/terms URLs plus genuine analysis/display permission evidence. The
ownership setting is not a third-party permission grant.

Only use private-network opt-in for a camera you control. Public sources should
leave it false. Hostnames are allowlisted and initial DNS addresses are checked;
HTTP snapshots validate redirects. OpenCV's FFmpeg transport internally follows
video redirects/HLS child requests: those subordinate requests are not fully
host-revalidated by RoadPulse. Use only trusted, authorized stream origins;
this is not a hardened arbitrary-playlist fetch service. Actual HLS/MJPEG/RTSP
compatibility depends on the installed OpenCV/FFmpeg build and remains unverified
here. Stream readers have five-second FFmpeg open/read limits and reconnect
backoff. Only one source is inferred at a time. No paid service is needed.
