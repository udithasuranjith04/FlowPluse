# Café person-detection reliability — focused scans

## What changed

- Full-frame YOLO person detection still runs on each sampled AI frame.
- When the CPU/MPS can keep up, two overlapping *in-memory* close-up passes
  recheck the left and right image regions. Each candidate is projected back to
  the original frame coordinates and near-identical boxes are merged.
- The scan automatically pauses for a short cooldown after repeated slow passes.
  System Health reports whether it is actively scanning or performance-limited.
- Weak single-frame candidates still require temporal evidence. A missed frame
  never counts a person. A weak detection at a previously confirmed location can
  recover after one miss, based on anonymous box overlap (not identity matching).
- The Live Café overlay no longer holds last-observed boxes when detection goes
  missing. This reduces misleading boxes that trail people across the video.
- Camera preview, scene discovery, alerts and shift-summary semantics are unchanged.

## What this cannot do

The system cannot reliably find a fully hidden person or tell whether two figures
behind a table are separate if the image lacks enough visible evidence. It is
not face recognition, person re-identification, staff classification or certified
headcounting. More close-up passes can introduce false positives; validate both
misses and extra boxes using known permitted scenes.

## Optional local comparison: YOLO11n vs separately installed YOLO11s

FlowPulse **does not download** a bigger model automatically. Only compare model
weights you have obtained and accepted explicitly. Using a local, permitted video:

```bash
cd ~/Documents/AI-ML/Projects/FlowPulse
.venv/bin/python scripts/compare_person_models.py \
  --video /absolute/path/to/permitted-cafe.mp4 \
  --baseline runtime/models/yolo11n.pt \
  --candidate runtime/models/yolo11s.pt
```

The comparison prints sample counts and timings; **more boxes is not proof of
better accuracy**. For a limited count-error check, make a CSV with human-counted
frame timestamps:

```csv
seconds,visible_people
10,5
25,7
40,6
```

Pass it with `--reference /absolute/path/to/visible_counts.csv`. This computes
mean absolute count error, not bounding-box precision/recall. For true detection
accuracy, label boxes for clearly visible people and score recall, precision,
false positives and tracking continuity separately. Use the same samples and
processing settings for any two models.

## Inspecting real performance

Use System Health → Technical diagnostics to read actual AI FPS, inference
latency, and focused-scan state. Disable any camera movement and use a fixed,
authorized view. A short prerendered demo is not validation of real queue times.
