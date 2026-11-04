# FlowPulse AI v1.1.0 — Café context and measurement trust (candidate)

Built on the **v1.0.0 clean source snapshot**. This is an incremental code patch, not a new product installation.

### Changes

- Live people count is hidden when the freshest AI result is stale/unverified; historical averages and sustained peaks use clearer, time-scoped descriptions.
- Recurring hotspot tiles can be explicitly labeled *Seating*, *Counter / pickup*, *Entrance / walkway* or *Other* by the operator. Labels stay in browser storage for the particular camera. Seating labels suppress misleading low-movement service suggestions. They **never** create staff/customer classification or queue detection.
- An interrupted, non-monotonic, or long-gap detection stream restarts the scene learning window.
- Offline annotated count evaluator supports an optional human-labeled `scenario` column with descriptive per-scene error slices.
- Added regression tests for scene interruption, current-count freshness, label persistence, and contextual guidance.

### Not part of this release

No camera driver, OBS connection, model weights, training, tracker choice, inference frequency, database schema, public-video ingest or identity processing changes. No human-counted real-camera measurements have been collected by this patch. No claims of certified accuracy or actual queue times.

### Validation status

- Backend regressions and syntax checks: see the accompanying patch-delivery report for actual results.
- Full frontend tests/typecheck, macOS camera acceptance and GitHub CI: **must be run by the developer** before tagging.
- See `docs/CAFE_V11_VALIDATION.md` for reproduction and acceptance steps.
