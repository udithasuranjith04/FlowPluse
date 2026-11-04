# More reliable café person detection (local only)

This upgrade improves **recall and visual stability**, not identity or job recognition.
It applies to real people-analysis sources; the generated vehicle fixture is unchanged.

## What the app now does automatically

- **More detail:** YOLO11n starts with a 960-pixel person-detection input rather than the model's ordinary 640-pixel input. This can help small/distant people occupy more model pixels. If five successive inferences exceed 420 ms, FlowPulse reduces the input to 832, then 736, then 640 pixels to keep the Mac responsive. The camera video stream remains independent of the AI rate.
- **Evidence for weaker detections:** instead of instantly dropping every person prediction below the configured confidence threshold, FlowPulse requests candidates down to 0.12 confidence points below that threshold (floor 0.18). A weak prediction is eligible only when a separate sampled frame confirms a similar overlapping person box nearby. Strong predictions are admitted immediately. If a later weak prediction matches an already accepted person, it can be admitted as a recovery. This is still not guaranteed to be a real person.
- **Fewer distracting overlay blinks:** for up to ~0.7–1.1 seconds, a missed *last observed* person box can appear as a faint, dashed **last seen · not counted** marker. These display-only markers are **never** added to counts, flow rules, scene discovery, queue signals, or shift history.
- **Explicit diagnostics:** the local status API reports `detector_input_size`, `weak_person_confirmations`, and `overlay_tracks` separately from current `tracks`, and the Camera Workspace shows effective detail size alongside video and AI rates.

The confidence threshold configured for a camera still controls which new detections are admitted immediately. Lower-scored candidates can be admitted only after additional model evidence. All short-term evidence and anonymous tracks stay in RAM and reset on stream discontinuity, camera change or stop. No person identity, face embedding, employee role, clothing category or unique visit is recorded.

## Limits you should disclose

1. **YOLO11n is small and imperfect.** Very distant, crowded, obscured, blurred or low-light people can still be missed, and lowering a candidate threshold can introduce false positives. A visible box does not prove correctness.
2. **A held overlay is not a live detection.** It shows the last observed location to reduce flashing. A person can move during that interval, so the overlay may temporarily lag the video.
3. **The displayed camera video may run around 10–15 FPS, while the AI samples around 2 FPS.** Counts update only when the actual model processes another frame. Higher input detail can reduce AI throughput; inspect the displayed `AI FPS` and `Detail` values.
4. **No role/identity inference.** Neither the detector nor the temporal gate can prove who is staff, who is a customer, whether a person ordered food, or how many distinct people visited.
5. **Do not validate on a filmed screen alone.** For actual accuracy, evaluate a fixed, authorized camera with known counts and review false positives, missed people, and view interruptions. A downloaded video can demonstrate processing, but it is not validation of a deployed café.

## Lightweight acceptance procedure

After `make lint`, `make test`, `make build`, restart FlowPulse, start OBS Virtual Camera or an authorized fixed live camera, and let the input remain stable. Check these states:

- Several visible people: most stable, sufficiently large visible people should acquire solid sampled boxes; some tiny/hidden people may still be missed.
- A confirmed person briefly missed: a *faint dashed* last-seen marker may remain briefly. **Visible people** should reflect only *currently confirmed detections*, not the faded marker.
- A changed scene/camera source: old overlays vanish; scene discovery resets on camera continuity problems.
- Smooth video should keep streaming when overlays are toggled, even when detection is slower.
- System health shows actual `AI FPS`. Compare a known manual count of people visible on selected sampled frames with FlowPulse's count. Record both missed detections and false detections; do not report accuracy before measuring it.

Ultralytics inference parameters, including `imgsz`, `conf`, and model performance:
<https://docs.ultralytics.com/modes/predict>
<https://docs.ultralytics.com/models/yolo11>
