# Authorized camera setup

**No real live camera is configured, verified, or bundled.** Publicly viewable does not imply permission to analyze, retain or retransmit video. RoadPulse never discovers or scrapes camera URLs.

1. Obtain a direct continuous video URL from the camera operator. Verify the video is continuous rather than periodically refreshed JPEGs.
2. Record the official provider/source page and terms. Obtain permission for automated analysis and for display/retransmission into this dashboard. Record access limits, attribution, geographic restrictions, allowed retention and the check date.
3. Install optional inference dependencies and weights with `make model`. Review [model licensing](LICENSING.md).
4. Copy `.env.example` to `.env`. Keep this file out of Git. Configure the fields below, using your actual authorized source. Restart `make dev` after environment changes.

```dotenv
ROADPULSE_CAMERA_MODE=live
ROADPULSE_CAMERA_URL=<authorized-direct-HLS-MJPEG-or-RTSP-URL>
ROADPULSE_CAMERA_ALLOWED_HOSTS=<exact-source-hostname>
ROADPULSE_CAMERA_NAME=My authorized road view
ROADPULSE_CAMERA_REGION=<region>
ROADPULSE_CAMERA_PROVIDER=<operator>
ROADPULSE_CAMERA_SOURCE_PAGE=<official-page>
ROADPULSE_CAMERA_TERMS_URL=<applicable-terms>
ROADPULSE_CAMERA_ANALYSIS_AUTHORIZED=true
ROADPULSE_CAMERA_REDISPLAY_AUTHORIZED=true
ROADPULSE_CAMERA_PERMISSION_NOTES=<specific-permission-evidence-and-access-limits>
ROADPULSE_CAMERA_PERMISSION_CHECKED=<YYYY-MM-DD>
```

5. Select the configured source in the dashboard. Check Diagnostics for actual frames, processed FPS, detector version and input quality. A successful TCP connection alone is not a successful inference test.
6. In **Camera & Zones**, refresh a paused frame, draw a monitoring polygon, add it to the draft and save the configuration. Configure ignore regions where useful. Calibrate thresholds with reviewed clips. Snapshot sources explicitly disable tracking and temporal observations.

For a privately owned local camera, explicitly set `ROADPULSE_CAMERA_ALLOW_PRIVATE=true` only after adding the precise hostname. The API must remain bound to localhost. Allowlisting checks the initial host, not every downstream HLS segment or redirect; configuration must be trusted.

To analyze a permitted local video, use `ROADPULSE_CAMERA_MODE=replay` and `ROADPULSE_REPLAY_PATH=/absolute/path/to/permitted-video.mp4`. Record permissions as above. This path is environment-only; uploads and arbitrary path APIs are intentionally absent. Configured file replay uses the pretrained model, not the synthetic color detector.

For periodically updated JPEGs, use `ROADPULSE_CAMERA_MODE=snapshot`. Expect `SNAPSHOT`, with temporal rules disabled. The installed FFmpeg build must support the provider's image endpoint. Diagnose failures honestly; never relabel snapshots as live video.

## Troubleshooting

- **Permission blocked:** supply both authorization flags, evidence notes and check date. The software records your assertion; it does not verify a legal permission automatically.
- **Model unavailable:** run `make model`, then confirm `ROADPULSE_MODEL_PATH` is a local weights file you trust.
- **Reconnecting:** check source expiry, internet connectivity, hostname allowlist, permission/access limits and format support. URLs are intentionally excluded from logs.
- **No observations:** save monitoring polygons; allow tracks to mature and a moving baseline to warm up; inspect input-quality and general-stop suppression in Diagnostics.
- **Too slow:** reduce sample FPS or resolution and measure again. Do not treat uncalibrated pixel movement as a real-world speed.
- **Display permission absent:** leave the source disabled. The application does not provide an analysis-only bypass that leaks images to the browser.

## Fintraffic current road cameras

The dedicated [Digitraffic workflow](DIGITRAFFIC.md) uses documented CC BY 4.0 rights with attribution, preset discovery and approximately ten-minute snapshots. No arbitrary stream URL, registration or paid inference is required. Enable `ROADPULSE_DIGITRAFFIC_ENABLED=true`, then browse/select a real station and preset in the dashboard. Generic source permission flags can remain false. Those flags still apply to unrelated live/file/snapshot sources.

This adapter does not use OpenCV VideoCapture for HTTP snapshots. It fetches bounded, conditional JPEG responses through a provider-specific client and passes new images into the existing local YOLO worker. No temporal rules or continuous vehicle identity run on these images. Official TMS speed/count values are displayed separately from per-image detections.
