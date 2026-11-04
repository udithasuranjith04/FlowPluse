# FlowPulse AI — portfolio evaluation protocol

Use a stable camera and a **consenting, controlled** demonstration scene. Do not record or upload identifiable video without additional permission. An operator independently counts ground-truth crossings and zone membership as the test runs.

| Trial | Ground-truth setup | What to record |
|---|---|---|
| Positive detection | One person enters, stands, leaves | Detection count, false negatives/positives, inference latency |
| Entry direction | 10 deliberate A→B line crossings | Number of reported entries, missing/extra crossings |
| Exit direction | 10 deliberate B→A line crossings | Number of reported exits, missing/extra crossings |
| Occlusion | Two consented participants cross each other | Track-ID switches, missed counts |
| Dwell | One person inside zone for 2× threshold | Event start latency, resolution after exit |
| Queue indicator | Three people linger in zone vs walk through | Possible-queue flags, false alarms and delay |
| Recovery | Stop/restart camera or disconnect iPhone | Camera release, reset, no reused track identity |
| Performance | 3-minute stable run | Processed FPS p50/p95 inference, dropped frames, staleness |

**Suggested reporting:** line-count absolute error = `abs(predicted - manually counted)` per direction; report missed and extra crossings separately. For person detector, annotate sample frames when permission allows and count TP/FP/FN. Avoid asserting a percentage unless actual labels and sample sizes are documented. Record camera height, angle, FPS and zone/line placement so results are reproducible.

**Current status:** no real iPhone-based accuracy experiment was performed in the patch environment. All rows are procedures, not results. Populate your portfolio evaluation with actual measured values after Mac acceptance.
