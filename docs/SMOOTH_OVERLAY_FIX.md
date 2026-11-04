# FlowPulse — Stable, honest live detection overlays

This is a **display-only quality improvement**, not a change to YOLO detections,
confidence thresholds, visible-person counts, zone monitoring, entry/exit
measurements, or shift statistics.

## Why boxes blink

The browser draws the fast, independent MJPEG camera stream and updates AI
boxes only when a slower person-detection sample completes. The previous
fixed 0.85-second expiry could fade a box completely between two legitimate
AI samples, particularly when processing slow or high-resolution frames.

## Original fix (v1.0)

- **Solid mint boxes** are actual detections from the latest completed AI
  sample. Their display expiry takes the observed processing FPS and measured
  processing delay into account, with a hard 1.8-second upper bound.
- **Faint dashed amber boxes** are *unverified last-seen locations* shown only
  after a missed AI observation, for at most 0.9 seconds after the last
  detection on the backend and 1.1 seconds including subsequent display age.
  They **never count as people**, trigger alerts, or affect tracks/shift totals.
- Existing anonymous track IDs let the browser ease a confirmed box's geometry
  between sampled positions. This is **visual easing, not optical flow** and
  does not claim video-frame-accurate movement.
- A paused, disconnected, stale, discontinuous or newly selected camera may not
  display held boxes. React does not recreate the MJPEG image on box changes.
- The overlay footer explains what solid and dashed outlines mean.

## Local acceptance test

1. Back up changed source files and stop `make dev`.
2. From the repo root, apply the incremental file ZIP. Run `make lint`,
   `make test`, `make build`, and `make dev`.
3. Use OBS Virtual Camera with a licensed/consented sample. Check that
   continuously visible people have steadier solid boxes without flashing
   off between otherwise healthy samples.
4. Move one person out of view. A last-seen hint, if any, should be dashed,
   amber, faint, and brief; no person count should be added by the hint.
5. Pause/stop the camera and check that boxes no longer appear as current.
   Test changing source and abruptly interrupting OBS.
6. Watch `System health`: if inference FPS decreases greatly or delays spike,
   the overlay still expires, rather than fabricating continuous tracking.

## Remaining limitations

At ~2 AI FPS, this can improve perceived stability but cannot know where a
walking person is in each 12 FPS preview frame. Motion and occlusion cause
box drift and occasional missed or swapped anonymous tracks. Test against
hand-annotated authorized footage before using reported counts to guide real
operational decisions. No raw footage needs to be saved for this adjustment.

## Follow-up stability fix (v1.1 feature branch)

The initial cadence-aware *opacity curve* could still visibly pulse at ~2 AI FPS.
The updated browser presentation now holds solid green at a **steady opacity**
between recent AI samples. If evidence is missing or delayed, it changes to a
brief, fixed-opacity amber dashed last-seen outline and then disappears. It
never predicts movement or increases counts. Repeated WebSocket messages for
the same AI frame do not refresh observation age.

This supersedes the original 1.8-second fade behavior **for the v1.1 browser**.
Detailed acceptance checks: [v1.1 stable overlays](V11_STABLE_OVERLAYS_ACCEPTANCE.md).
