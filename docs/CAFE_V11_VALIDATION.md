# FlowPulse v1.1 — acceptance and evidence plan

This is an **upgrade candidate**, not a claim that model accuracy or customer ROI has been established. Use a fixed authorized camera/OBS Virtual Camera. If OBS replays a video, describe it as **prerecorded footage analyzed live**.

## What changed, and how to test it

| Improvement | Mac acceptance observation | Pass condition |
| --- | --- | --- |
| Live people estimate | Stop and disconnect OBS while Live café is open | Current people number becomes `—` after stale/error status; the dashboard explains it is waiting for a verified sample; shift history can remain displayed with historical labels |
| Different count time windows | Compare Live café and Shift summary | *Visible now* is a current frame estimate, *highest sustained* is a five-sample median over the shift, and *average* is the sample mean over the shift; differences are expected |
| Scene context | Label a discovered hotspot as **Seating** and inspect Service alerts | Low movement in that tile remains a scene observation but is not itself shown as a service issue; counter label offers only a review suggestion, not an asserted queue |
| Tag reset | Move camera deliberately, allow movement warning; or select **Clear my area labels** | In-browser scene labels are cleared. Some repositioning may escape camera-motion detection: manually clear labels when changing angle |
| Scene interruption | Disconnect/reconnect the source | The hotspot sample restarts and old patterns are not considered recent until enough healthy frames accumulate |
| No false claims | Read demo and GitHub README | No unique visitors, staff identities, waiting times, sales, service speed, or certified occupancy are claimed |

The scene context label is for a **6×4 image grid tile**, not a physical floor polygon. The software does not automatically locate a café counter, doorway, seating area, or queue. These labels do not change model inference or produce a customer count. Tags persist only in that browser's local storage for the camera identifier; clear the browser's site data to remove them all.

## Ground-truth protocol (do not fabricate data)

1. Obtain permission to analyze the fixed café video. Choose **at least 50–100 distinct processed frames**, sampled across separate moments (not many near-duplicate consecutive frames). Include empty, clear, busy/crowded, occluded, and low-light views where available. This is an initial *portfolio* evaluation, not a statistical guarantee for other venues.
2. For each frame, record the same frame ID used by the detector and **manually count visible people** independently. Include obscured people only if a human can actually verify them; publish that labeling rule. A count from a slightly different OBS video instant is not ground truth for the processed frame.
3. Save your CSV **outside Git**, preferably under `runtime/`, with fields:

   ```csv
   frame_id,reference_people,detected_people,scenario
   example-frame-1,3,3,clear
   example-frame-2,5,4,occluded
   ```

   The rows above demonstrate the **format only**; they are **not measurements**. Valid `scenario` values: `clear`, `crowded`, `occluded`, `low_light`, and `other`. The fourth column is optional for older evaluation files.
4. Run the offline evaluator:

   ```bash
   .venv/bin/python backend/scripts/evaluate_counts.py runtime/your_manually_labeled_counts.csv
   ```

   Report overall MAE (people/frame), RMSE, signed bias, exact fraction and per-scenario MAE **with sample sizes**. If a group has very few frames, say so. These metrics do not establish recall, track continuity, unique visitors, or queue accuracy.
5. Optional: using exactly the same annotated timestamps, compare installed models with `scripts/compare_person_models.py`, as documented in `docs/CAFE_DETECTION_QUALITY_TRUST.md`. Report video source/license, input size, device, median runtime and count/box errors; do not call one model better based solely on larger weights or a smoother demo.

## Release gate (run on your own Mac)

```bash
cd ~/Documents/AI-ML/Projects/FlowPulse
patch --dry-run --batch -p1 < ~/Downloads/FlowPulse_v1_1_Cafe_Intelligence.patch
# Apply only if the dry run reports no failed hunks.
patch --batch -p1 < ~/Downloads/FlowPulse_v1_1_Cafe_Intelligence.patch
.venv/bin/python -m ruff format backend scripts
make lint && make test && make build
make dev
```

Verify camera connect, preview, start, pause, stop, unplug/reconnect, delayed AI frames, and no stale current count. Review browser console for errors. Keep the repository private until a secrets/footage/license check. If you see any failure, **do not force** the patch, reset the repository, or publish a v1.1 tag yet.

## Known limits still requiring real-world work

- Detection can miss or duplicate heavily occluded people. A single view cannot reveal fully hidden persons.
- 2-FPS-ish inference is **not** per-video-frame motion tracking. Short-lived visual hints remain uncounted.
- Browser-stored scene labels can be incorrect if you reposition a camera between sessions without detecting a view shift.
- No annotated evaluation results were generated during patch construction. No claim of production deployment, legal compliance, or commercial-grade accuracy is made.
