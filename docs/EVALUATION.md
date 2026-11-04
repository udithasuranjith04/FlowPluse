# Evaluation and performance

No real-world event accuracy, recall, precision or false-alert rate has been measured yet. No authorized live feed or permitted real evaluation footage was supplied for this build. The generated replay is a deterministic software integration test, not a model or event-accuracy benchmark.

`make benchmark` measures 160 generated frames representing an 80-second scenario. It writes actual elapsed time, detector latency p50/p95, processing throughput, peak process RSS, hardware/OS/Python information and emitted event counts to `runtime/benchmark.json`. It exits unsuccessfully if either expected observation type is absent. Do not compare this fixture-only color detector to YOLO results. The runtime dashboard measures the active detector separately.

## Real-data evaluation procedure

1. Obtain footage with explicit analysis and evaluation/retention permission. Record source and model versions, camera geometry, sampling rate and thresholds.
2. Hand-label independent event and non-event windows. Include signal stops, empty lanes, moving shadows, queues, night/rain, heavy occlusion, frozen frames, cuts and stream loss.
3. Define a temporal matching tolerance before looking at results. Match predicted events to labeled windows one-to-one. Count unmatched predictions as false alerts, not as duplicate positives.
4. Report sample size, observation hours, event-level precision and recall, false alerts/hour, detection delay and confidence limits. Separate cameras and conditions; report uncertain labels separately. Include inter-reviewer disagreement where possible.
5. Benchmark YOLO on the actual target CPU using representative frames after model warmup. Record resolution, hardware, OS, model/weights hash, p50/p95, memory, FPS and processing/frame age. Upstream-to-browser delay is unknown without trustworthy source timestamps.
6. Publish failure cases and the exact configuration. Do not infer real speed or distance from normalized image-plane movement.

Known risks: association switches for overlapping vehicles; red-light stops; unobserved zones; stationary vehicles during baseline warmup; camera movement too subtle for the cut heuristic; pixel-identical versus visually similar frozen frames; severe frame drops; reflections and lighting; unsupported provider formats and signed URL expiry. The system has no scene calibration or signal-state knowledge.

## Pretrained detector timing

After `make model`, configure an authorized local replay and its permission evidence in `.env`. `make benchmark-model` measures the actual optional detector on 100 decoded frames after five warmup frames, and writes `runtime/benchmark-model.json`. It retains no input frames and omits source paths from the report. The reported detector-only FPS excludes decoding, tracking and UI delivery. Pretrained-model execution remains blocked: optional dependencies and weights are unavailable, and no permitted real clip is configured. No pretrained-model timing is claimed. See the [current verification results and generated-replay measurements](VERIFICATION.md).

`make verify-model` now executes actual installed YOLO11n weights on original generated pixels and writes `runtime/model-smoke-cpu.json`. It is an execution smoke, not road-camera accuracy evaluation. `make verify-digitraffic` is a separate small real API/JPEG/inference probe with optional independently selected TMS station. Its report must say `success: true` before reporting that provider flow as passed; this restricted session's report says false. Snapshot counts are per-image detections, and cannot validate temporal tracking or stopped-vehicle/congestion events.
