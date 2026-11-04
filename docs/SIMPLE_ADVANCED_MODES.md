# FlowPulse AI — Simple and Advanced analytics

The camera, YOLO detector and tracker are shared. There is **no second inference
pipeline**. Person count history is held in process memory only (at most 90 healthy
processed frames, typically ~45 seconds at 2 FPS). It is not stored in SQLite,
serialized as video, or linked to persistent identities. It clears on stop, source
switch and input discontinuity. A backend restart also clears it.

## Simple mode (default)

1. Open the dashboard; select your local Mac/iPhone camera and grant explicit consent.
2. Preview the camera to validate changing frames, then click **Start monitoring**.
3. The dashboard immediately shows *people currently detected*, *anonymous active
   tracks*, *processed FPS*, and a *recent visible-person count trend*.
4. No spatial configuration is required. Preview is not an evidence-recording mode.

**Not provided in Simple mode:** real building occupancy, automatic entrance discovery,
entry/exit counts, dwell/queue judgments, or identity tracking. The visible count
is a per-frame estimate and can fluctuate with occlusion and detector confidence.

## Advanced mode (optional)

Switch to **Advanced** for configured entries/exits, zone occupancy, dwell candidates,
and possible queue buildup. Click **Add a zone or counting line** or **Quick zone
presets** to open **Zones & lines**.

The quick presets are saved immediately to the existing per-camera configuration API:

- **Use entire frame**: adds a 98%-size monitoring polygon. It can produce
  irrelevant dwell/queue candidates, so use it only for controlled demonstrations.
- **Add central waiting area**: an editable central polygon for a starting point.
- **Add starter entrance line**: a horizontal line through the center. **It is
  not an automatically discovered entrance.** Move people across a properly placed
  line before interpreting counts. For another location, delete this starter
  line and draw a custom two-point line. Use **Reverse direction** to flip its
  entry/exit semantics, then click **Save configuration**.

Templates add to existing zones/lines and reject duplicate IDs; they do not
silently erase saved configurations. Draft manual edits need **Save configuration**.
Saving configuration resets event baselines and per-session crossing counts.

## Evaluation

Use a fixed camera looking at a permitted controlled space, consenting
participants, and manual reference counts for a sample of crossings. Record
false positives, missed persons, ID switches, missed/duplicate crossings,
processed FPS and camera limitations. A video played on another screen is useful
for plumbing checks but not for real-world counting accuracy.
