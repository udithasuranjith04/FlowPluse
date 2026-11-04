# FlowPulse automatic analytics — design and limitations

This release adds a **no-configuration** analytics path on top of the existing local iPhone/YOLO/anonymous-tracker pipeline. Manual geometry is entirely optional for these **image-plane** measurements.

## Immediately available after camera consent

- Live visible-person detections, temporary session track count and measured FPS.
- Bounded count history, recent average, peak, and rising/steady/falling count trend.
- Coarse 3×3 image sector with the most observed person footpoints over the recent frame window (only after sufficient healthy frames).
- Anonymous left→right/right→left **crossings of the image center**, when actively monitoring. No stored person identities, faces, or image capture history.
- Healthy frame filtering, reset on source stop/change/discontinuity, no alerts on preview/snapshot data.

Automatic summaries are in memory in the `automatic_insights` field of `/api/system/status`, containing only aggregates and a limitations note. Never send raw images or cross-session identifiers to external services.

## What cannot be safely automated from arbitrary video

Camera ownership/permission, consent of participants, physical entrance/exit semantics, permitted waiting areas, reliable queue identification, actual room occupancy, and accurate crowd density require ground truth, physical context, and/or calibration. The centerline is a geometric image reference, **not** a doorway. A busiest 3×3 sector is **not** a queue. A rising visible-count trend is **not** a congestion alarm.

The existing editable entrance-line and monitoring-zone tools therefore remain as advanced controls. Full-frame and ≥85%-of-frame zones are **count-only**, avoiding false dwell/queue events caused simply by people staying in camera view. Previously saved observations are not erased or relabeled retroactively.

## Quality / evaluation

- Use a stationary, authorized camera and consenting participants; do not use second-screen videos for final accuracy claims.
- Verify 1, 2 and several people, exits from the field of view, occlusion, reconnect/reset, and camera movement.
- With a known physical entrance, configure the oriented line and measure precision/recall of directional crossings against manual counts. At 2 FPS, expect missed associations for fast motion.
- Report FPS/latency, missed/duplicate crossings and limitations in the portfolio. Unit tests validate deterministic logic, **not** field accuracy.
