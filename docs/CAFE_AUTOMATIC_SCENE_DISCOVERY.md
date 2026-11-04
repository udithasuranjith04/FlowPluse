# FlowPulse Café — automatic scene discovery

## What it does

The app automatically learns **where anonymous camera detections regularly appear** and **where tracked footpoints tend to move or linger**. No user-drawn polygons, uniform labels, face data, customer identities, or model downloads are required. The scene map appears in **Live café** and **Camera setup** after a sufficient window of stable, healthy monitored frames.

- A bounded rolling buffer holds at most 360 frame summaries (24 per-frame cells; no frames or track IDs).
- Footpoints from the existing YOLO11n `person` detections populate a 6×4 image grid. Other object types do not contribute.
- Anonymous track maturity and motion provide **longer-stay**, **movement**, or **frequent presence** pattern labels. These labels describe activity, not people.
- Candidate hotspots are selected only after at least 36 frames, 15 seconds of observation and 30 person-presence samples. Adjacent candidates are suppressed so the user sees distinct areas rather than duplicate tiles.
- Scene data starts fresh on stop, source switch, monitoring reset or capture continuity reset. Preview is excluded. No scene coordinates are written to the review database.
- "Repeated" / "Emerging" describe how often a location was occupied in the sample window, **not an AI probability of a café counter or staff area**.

## What it does NOT do

The system does **not** know whether a person is staff or a customer, infer their job from clothing, identify kitchen/service counters, recognize restaurant tables, determine exact waiting times, or prove a physical queue. A staff member delivering food to a table appears as anonymous activity just like anyone else. Appearance-based role guessing is not robust across uniforms, casual clothes, lighting, or occlusion.

If a café needs independently verified staff exclusion, the existing one-time **staff-only half** filter remains available under **Camera setup → Optional: exclude a known staff work area**. Its output is still only a *people outside an area* estimate. Do not present the two methods as the same or automatically switch a user's staff-region setting.

## Validate on a permitted real camera

1. Fix the camera in a legal, authorized location and notify participants. Do not move it during a session.
2. Point it at a café scene with an observable walkway and a separate standing/seating area; ensure people can be seen with minimal overlap.
3. Allow approximately 30–90 seconds of monitoring. Check that the scene map marks a frequently occupied area; verify placement by comparing with **actual image location**, not role assumptions.
4. Observe 5–10 controlled walking passes. Record whether the movement hotspot covers the expected walkway. Note misses and track discontinuities at ~2 processed FPS.
5. Have consenting participants stand or sit in one location for at least 15 seconds. Check if longer-stay activity appears and whether it could just represent seating rather than a queue.
6. Repeat with the camera view changed *after stopping* and verify previous scene hotspots reset. Preview must not build monitoring hotspots.
7. Record false regions, camera angle, lighting, FPS, occlusions and any overlay-vs-frame mismatch in your release notes. These observations are not a validated accuracy statistic until formally scored against ground truth.

## Future research (not delivered by this patch)

For a reliable staff/guest split across a floor, combine consented operational context (e.g., a staff opt-in source or POS/service data) and a measured spatial flow baseline. Adding clothing classifiers or cross-camera individual identification without independent evaluation would add false confidence and privacy risk. Optional cross-shift aggregate comparison now exists behind explicit local opt-in. It is not verified against camera repositioning between days, and should be treated as an exploratory reference, not a calibrated benchmark.
