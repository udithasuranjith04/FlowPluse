> **Historical RoadPulse vehicle demo only.** This is not the current FlowPulse Café portfolio walkthrough. Use [the café demo](CAFE_DEMO.md) instead.

# Demo walkthrough (about two minutes)

1. Run `make setup` once, then `make demo`. Open http://127.0.0.1:5173.
2. The header and video explicitly say **REPLAY DEMO / SYNTHETIC REPLAY**. Explain that the pixels are generated and the color detector only validates the software pipeline.
3. Watch moving vehicle boxes and anonymous track IDs. The cyan car stops early in the 80-second scenario while other lanes keep moving. With default settings a potential stopped observation should appear after track maturity plus the stationary interval (roughly 20–25 seconds).
4. Click the observation and inspect its measured motion, observed duration, saved thresholds and quality flags. Acknowledge it, mark it a false alarm, then reset review if desired. These actions persist in SQLite.
5. Around the second half of the scenario, a generated queue increases occupancy and reduces movement. After the warm baseline and sustained duration, a congestion-buildup observation should appear. Clearance resolves the lifecycle while preserving its human review label.
6. Open **Camera & Zones**. Refresh the paused frame, add a polygon using mouse clicks or the coordinate inputs, name it, add it to the draft and save. Saving restarts temporal baselines; explain this before expecting the same event timing.
7. Open **Diagnostics** to show actual detector timing, FPS, dropped/superseded frames, quality flags, baseline status and logs. Fixture detector benchmarks do not measure YOLO performance.
8. Open **Events** to filter, review and export metadata. Pause the source to demonstrate the offline state, then restart/reconnect.

The scene loops at 80 seconds with new tracking context. Replay timing is not an accuracy result. Run `make test` and `make benchmark` for the deterministic accelerated integration scenario.

## Screenshots and recording

`make e2e` starts a synthetic backend and frontend, exercises event review and writes `docs/screenshots/overview.png` and `mobile.png` from the actual running application. Run `cd frontend && npx playwright install chromium` first. A screen recording can follow the walkthrough above; no demo recording is claimed until one is actually produced.

Do not make a screenshot look live when it is replay. Do not capture or publish an upstream camera until its operator permits display, recording and redistribution.
