# FlowPulse AI — implementation and Mac acceptance

This migration modifies an existing RoadPulse AI codebase **without replacing it**. People-flow rules are separate from the prior vehicle-event engine. Historical traffic events in SQLite remain valid historical records and are not relabeled as people events.

## Changed capabilities

1. `ROADPULSE_DETECTION_TARGET=person` makes the actual YOLO model select COCO person class 0 on real camera frames. `vehicle` still supports earlier behavior; the generated demo remains legacy synthetic traffic.
2. Real continuous-video input uses anonymous per-session tracker IDs, current-frame `visible_people`, polygon footpoint occupancy, and directed crossing lines. No identity or face embedding exists.
3. Counter direction: for line endpoints A→B, compute a signed point-to-line distance. Crossing from negative to positive increments **entries**; reverse increments **exits**. A dead zone and per-track cooldown reduce double counts. A track must be mature and within the segment extent. Camera orientation and user-defined endpoint direction determine practical interpretation.
4. `extended_dwell` events arise from sustained membership in a monitoring polygon. `possible_queue_buildup` events require sustained >= configured people with a configurable proportion of low-motion tracks; neither identifies intent.
5. Snapshot mode, preview-only mode, bad-quality input and interrupted sessions suppress/reset temporal rules. Per-session crossing counts reset; archived observation metadata remains in SQLite.
6. Per-camera configuration is backward compatible: existing JSON without `lines` or new `RuleConfig` settings acquires validated defaults; the database schema is unchanged.
7. Existing road-specific demo rules remain usable for regression testing only, not as evidence of FlowPulse evaluation.

## Apply migration safely

Create a backup before patching. Apply the cumulative patch **once**, not on top of the earlier Phase 1 patch. It is based on the original uploaded `FlowPulse-migration-source.tar.gz`.

```sh
cd ~/Documents/AI-ML/Projects/RoadPulse-AI
patch --dry-run -p1 < ~/Downloads/FlowPulse_Complete_Migration.patch
patch -p1 < ~/Downloads/FlowPulse_Complete_Migration.patch
```

Do not force the patch if `--dry-run` fails; provide the failed hunk and file. Set `ROADPULSE_DETECTION_TARGET=person` in `.env`, then `make lint`, `make test`, `make build`, `make dev`.

## Controlled live-camera acceptance

1. Quit QuickTime and other camera apps. Keep a connected and compatible iPhone ready. Check enumerated camera devices in `cd backend && ../.venv/bin/python -m app.avfoundation`. The iPhone index is **not guaranteed** to remain 1.
2. Start RoadPulse. Select **My Live Camera**, select the actual iPhone by name, check the camera-control consent checkbox, preview and start the camera. See changing, genuinely live frames with YOLO person boxes when a consenting person is present.
3. After starting a real camera, in another terminal run `make verify-people`. Expect a positive `pass` for at least two distinct fresh frames. Separately note `positive_person_detection_observed` and actual FPS. If the latter is false while a person is clearly visible, investigate model inference and camera scene.
4. On **Camera & Zones**, define a monitoring polygon inside the image and save. Test one consenting participant entering/leaving this zone and record observed `flow.zone_counts` in `http://127.0.0.1:8000/api/system/status`.
5. Draw a **two-point counting line** crossing the participant's walk path. Save. Walk across once in each direction, slow enough for 2 FPS; expect one entry then one exit when the track survives. Reversing endpoint order reverses count semantics.
6. With one person remaining inside the zone for more than the `flow_dwell_seconds` threshold, check an `extended_dwell` observation. With multiple consenting participants standing inside for more than `flow_queue_seconds`, check **possible** queue observations. A single stationary person alone should not trigger queue alerts.
7. Stop camera in UI. Confirm released hardware and zero new frames. Verify counters reset after new session. Change camera source and confirm previous capture is released. Verify that snapshots and synthetic legacy demo never falsely generate people-flow events.
8. Record actual results and any false detections/ID switches. Do not claim that unit tests prove behavior on a real iPhone.

## Known limitations / portfolio honesty

- Low sampling FPS and lightweight spatial association can lose track IDs or miss fast crossings. The line counter's orientation is arbitrary until configured by the operator.
- No cross-session persistence for people counts. Zero live people does not imply zero room occupants outside the view.
- Queue indicator uses sustained low image-plane motion and group size, **not** verified queue behavior or social intention.
- Detection confidence is not an accuracy percentage; validation must use controlled hand-labeled trials.
- The original traffic adapters and labels in some legacy source UI remain for backwards compatibility. Primary FlowPulse mode is the owned live camera and person-focused dashboard.
- No raw frame/video recording by default, but the app renders live images to the operator. Use only with informed consent and applicable notice.

## Verification record

At patch-production time: backend tests were run in a container environment with mocked camera/provider data; live iPhone AVFoundation capture and full frontend build were **not** available. Run Mac acceptance steps and record actual measurements separately.
