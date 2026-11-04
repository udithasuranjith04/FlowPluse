# FlowPulse Café — Detection Quality & Trust

This release improves *measurement honesty*, not person identification or guaranteed detection accuracy. The existing smooth MJPEG stream remains independent from sampled YOLO inference. Local camera preview and operator consent remain unchanged.

## What is actually measured

- **Current people in view** is the number of current-frame person boxes admitted by the existing evidence gate. It can miss people behind pillars or furniture, double-count occluded figures, or include staff.
- **Sustained high count** is the highest median of five consecutive *healthy monitoring-frame counts*, not a certified occupancy limit. This prevents a single isolated high sample from dominating the owner dashboard; it does not prove that a high count is correct. The original **raw maximum** remains visible in Shift Summary notes and System Health.
- **Close-up proposals suppressed** counts same-frame detection boxes merged as likely duplicates. It is *not* false-positive precision. Nearby people who overlap heavily can still be difficult to distinguish.
- **Sampled green boxes** are positions from the last YOLO sample. On the smooth video, the v1.1 browser keeps the solid box steady for a bounded period between recent AI samples instead of fading on every timer tick. A missed or delayed sample may briefly appear as a dashed amber **unverified last-seen hint**; this never changes counts or alerts. Boxes are **not** tracked on every video frame. Status updates are more frequent, but model inference workload is unchanged.
- **Model choice** stays YOLO11n until you test a larger model on your Mac against human-checked sample frames. The software never automatically downloads or switches weights.

## Collect ground-truth samples ethically

Use footage you have permission to analyze. Prefer a *fixed* camera and short, varied moments (empty, busy, tiny people, partial occlusion, two people at one table). Keep the scene fixed; moving-camera footage invalidates stable-area interpretations. Use at least 20 varied frames to begin assessing count error, and substantially more for a meaningful deployment validation. A single café video does not establish general accuracy.

You can create **count labels** manually in `runtime/visible_people_reference.csv`:

```csv
seconds,visible_people
10,5
20,7
30,6
```

Or create **person rectangle labels** at selected timestamps for more useful precision and recall. Coordinates are normalized by the original video width and height (range 0–1); no person IDs are needed:

```csv
seconds,x1,y1,x2,y2
10,0.12,0.20,0.18,0.67
10,0.38,0.22,0.46,0.71
20,0.40,0.18,0.51,0.76
```

These examples are *file-format examples*, not ground truth for anyone's footage. Store such files locally. Never claim accuracy from self-generated YOLO labels.

## Benchmark a larger model (optional)

First obtain `yolo11s.pt` from a legitimate Ultralytics distribution into `runtime/models/yolo11s.pt`. This project does not bundle or download it. Read the model's license and your intended commercial-use conditions before product distribution.

```bash
cd ~/Documents/AI-ML/Projects/FlowPulse
.venv/bin/python scripts/compare_person_models.py \
  --video "/path/to/your/authorized-fixed-camera.mp4" \
  --baseline runtime/models/yolo11n.pt \
  --candidate runtime/models/yolo11s.pt \
  --boxes runtime/person_boxes_reference.csv
```

`--reference runtime/visible_people_reference.csv` can replace `--boxes` if only counts are available. With boxes, the report includes per-frame one-to-one IoU≥0.5 precision, recall, F1, missed/false boxes, mean absolute count error, and median/slowest inference times. With only counts, it reports **count error, not recall**. Without human labels it reports **relative counts and speed, not accuracy**.

The benchmark uses a preselected set of frames, full-frame and adaptive close-up scanning, and **strong-confidence detections**. It is a comparative development tool, not a full uninterrupted shift simulation or a certified benchmark; temporal weak-candidate confirmation is not simulated on spaced-out samples.

Only if a candidate offers meaningful measured gain at acceptable latency should you switch models. FlowPulse already supports a local model path via the `ROADPULSE_MODEL_PATH` environment setting; select the candidate weight file, stop monitoring and restart the backend. Do not change weights in the middle of a session. Keep a backup of your previous configuration.

## Acceptance checks before posting a LinkedIn demo

1. `make lint`, `make test`, `make build` pass on your actual Mac. These tests do **not** validate recognition accuracy.
2. Confirm that the OBS Virtual Camera source is selected by name. Video should remain smooth when toggling green boxes. Count estimates must never be presented as verified customer totals.
3. Compare the same person positions in video and sampled overlays. Fast movers may still move between the model's ~2 FPS samples; stale coordinates must become unverified amber hints and then disappear, rather than linger as confirmed green boxes.
4. Check System Health for close-up proposals added/suppressed and raw peak versus sustained high. Compare a known count manually with the displayed *current* count at the same moment.
5. Use only footage with redistribution rights and disclose **"Prototype demonstration using prerecorded café footage"**. Live **processing** of prerecorded video does not mean live customers at an operating café.

A successful run remains a **portfolio prototype**, not proof of universal people-count accuracy, staff recognition, customer visit tracking, exact wait time or service quality.
