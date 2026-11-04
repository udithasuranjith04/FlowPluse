# v1.1 — stable sampled overlays (visual reliability fix)

This incremental fix changes **only the browser display of detection boxes**. It does not adjust YOLO thresholds, person counts, tracking, saved records, or the OBS video connection.

## Why green boxes blinked

In v1.1 the browser multiplied every solid box by the same age-based opacity curve. At ~2 AI FPS (versus ~12 preview FPS), those boxes faded together between model results; intermittent missed detections also removed outlines. A smoother preview does **not** create faster inference.

## What changes

- Solid green outlines remain visually steady between **recent confirmed AI samples**, rather than pulsing with each browser timer tick. The UI never fabricates intermediate positions.
- Each new inference result updates geometry; short CSS easing only reduces visual jumping.
- If a new sample omits a person, a recently confirmed outline becomes a **dashed amber “last seen · not verified”** hint, then disappears. It is not counted or called a confirmed person.
- If AI processing stalls, confirmed outlines also turn amber and expire at a hard deadline. The UI clears on backend error, paused/stopped camera, source revision change, critical camera-quality flag or samples older than 3 seconds.
- Repeated WebSocket status messages for the same inference do not extend an outline's life. Very similar boxes can keep a visual element stable through brief anonymous tracker-ID changes; this does not associate people across visits or alter analytics.

## Mac acceptance checks

1. On your v1.1 feature branch, run `make lint && make test && make build` and resolve any reported errors.
2. Start OBS Virtual Camera and `make dev`. In Live café, enable *Overlays* and observe the sample for **2–3 minutes**, not just a screenshot.
3. While one clear person stays in view, check that the box is mostly steady instead of repeatedly dimming/brightening. The box may still shift at each actual AI detection; it is **not video-frame tracking**.
4. When the detector loses that person for one processed frame, check for a brief **amber dashed** hint rather than a solid green false detection. If the person leaves, the hint must disappear.
5. Pause/stop, switch cameras, disconnect OBS, and reconnect. Old boxes must disappear; the video stream must not repeatedly reload from inference updates.
6. In System health, record `Video FPS`, `AI FPS`, `processing_delay_ms` and any quality flags. If a visible person repeatedly goes undetected, that is a **model accuracy** issue, not a box animation issue.
7. Keep your v1.0 GitHub release untouched until these checks pass on your Mac.

## Remaining limitations

This improvement does not make a ~2 FPS detector run at 12 FPS. Boxes deliberately lag motion between AI samples; occlusion, missing people, camera perspective and duplicate detections still require annotated evaluations. This change is a *visual stability and measurement-integrity fix*, not evidence of improved people-count accuracy.
