# FlowPulse Café · Automatic scene and shift intelligence

## Owner workflow

1. Go to **Camera setup**. Select your own authorized Mac/iPhone camera, preview it, then start monitoring with a **fixed** view. Camera preview alone never collects shift or hotspot measurements. No video file upload, wired screen-mirroring testing, or video playback controls are provided.
2. Open **Live café**. The automatic scene map shows up to three areas of observed visibility, lower motion, or person movement over the camera frame. No manual zone drawing is needed for this activity map.
3. An area can be occupied in many frames by **one seated person**. A separate occupancy period means an image cell was occupied after being empty; it is not a unique visit, a new person or customer arrival. The map shows an approximate sampled time, processed-frame count and occupancy-period count.
4. **Service alerts** only promote a sustained count increase to attention when there is enough recent healthy data (at least 72 frame samples and 30 seconds). Low-motion hotspots remain informational—not inferred queues or staffing shortages. A confirmed waiting-area rule is still needed for zone-specific queue hints.
5. **Shift summary** describes the current monitoring session, not sales, order throughput, customer retention or exact wait time. The session resets when the camera stops, changes source or its temporal observations become unreliable.

## Camera motion safety

Large global image changes and coherent background motion can trigger camera-motion flags. FlowPulse resets in-session activity evidence when flags occur. A detected viewpoint change marks the session as unsuitable for saved historical comparisons. The owner sees a warning and the automatic scene map asks for a fresh fixed-camera session. Optical flow is a **heuristic**, not a guarantee that all camera motion was detected.

## Optional local shift memory

- Disabled by default, stored only on the local Mac in the existing SQLite database.
- Saves only date, camera ID, staff-area setting, valid sample count, approximate monitored duration, average people visible and peak count. No raw frames, faces, identities or individual trajectories are stored in this feature.
- Requires **300 healthy processed frames and at least 240 seconds** of the same continuous monitored session. Viewpoint movement detected during a session blocks saving that session.
- Keeps up to 60 records for at most 30 days; off/erase deletes stored summaries. Existing database tables are retained, and older short records are excluded from the new historical comparison.
- A comparison appears only after at least three eligible records for the same device ID and staff-area setting, and only after the current session has run for four minutes. It uses the median and observed range of previous shift averages, not a predicted benchmark.
- Camera **device ID and staff-area setting do not prove camera angle, venue layout or hour-of-day match**. The application cannot verify calibration across days. Interpret comparisons as exploratory estimates, not certified staffing advice.

## Validation before real use

Use a fixed, permitted camera with notified participants. Compare visible counts against independent manual labels for time-stamped frames and report false positives, missed people, moving-camera incidents, glare and occlusions. Separately observe at least 10 controlled movement passes and a seated participant, checking that the scene map does not call them repeat customer visits. Test an intentional camera pan, ensure the warning persists and the shift is not saved. Run `make lint`, `make test`, `make build`, and review `docs/RELEASE_CHECKLIST.md`. None of those software tests alone establish field accuracy.

## Remaining limitations

This system detects people and anonymous activity regions; it does not recognize staff versus customers from clothing, food delivery or body appearance. A seated patron and a waiting patron may look the same to the current detector. It does not infer table turns, real-world location, service speed, exact dwell time, purchases or visitor identity. The project still contains optional legacy provider/replay infrastructure for backwards-compatible developer use; it is not part of the café owner workflow.
