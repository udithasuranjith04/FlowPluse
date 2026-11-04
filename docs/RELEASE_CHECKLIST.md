# FlowPulse AI — release / portfolio acceptance

This checklist distinguishes **software checks** from **measured computer-vision performance**.
No benchmark results should be entered until collected from a permitted scene.

## Startup and UI

1. Launch `make dev` with camera disconnected. Refresh the browser. The branded
   **Understand spaces. Respect people.** screen appears while initial local
   status is loading and then disappears. With a stopped backend, the page must
   show an error and Retry rather than displaying false live metrics.
2. Use the dashboard with a narrow browser viewport, browser zoom, and keyboard
   Tab/Enter. Confirm the menu, camera consent, and observation review are usable.
3. Refresh while a camera is active: no additional camera sessions should be
   opened; reconnect to the already-running local backend stream.
4. Start a camera only after explicit operator consent. Verify preview and stop
   release resources in macOS Camera settings. The startup screen must never open
   a camera by itself.

## Local camera and model

- Run `make lint`, `make test`, `make build`, and `make verify-people` while the
  camera is running. Save the output as an acceptance artifact (remove private
  paths and source details before publishing).
- Exercise start/stop/reconnect at least three times. Inspect frame age,
  stale-frame messaging, observed FPS, track resets, and retained data.
- Move the iPhone as little as possible during directional-count tests.

## Count accuracy evaluation

For a small, diverse authorized evaluation set, select frames sampled at known
intervals. Have a person manually verify the **number of people visible** in
those frames. Record the detector's count from the **same processed frame**.
Do not use another screen's video or a different point in time as reference.

Copy `docs/counts_template.csv` into a separate local file and add your real, manually annotated frame counts. Do **not** commit private IDs or related media:

```csv
frame_id,reference_people,detected_people
```

One row per **real** annotated frame. Run:

```sh
.venv/bin/python backend/scripts/evaluate_counts.py /path/to/your/counts.csv
```

Reports MAE, RMSE, mean bias, exact-count fraction, and within-one-person
fraction. These are **count accuracy** metrics, not per-person precision/recall,
identity stability, doorway-crossing accuracy, or queue recognition metrics.
Don't claim those without separate ground-truth labels and protocols.

## Known scope limits

- Automatic image-midline crossings are not entrance/exit counts.
- A preset waiting area is only a geometric template. It is not a discovered queue.
- Full-frame regions are counts only by default; historical observations remain
  in the local database and may require human review.
- Very low FPS, screen filming, motion blur, perspective, and occlusion can
  produce track ID switches and missed people. The project is not a certified
  occupancy census or an autonomous decision system.

## GitHub v1.0 acceptance (complete before tagging)

- [ ] Run `python3 scripts/release_prep.py` and resolve any tracked sensitive-file warnings. Move old patch remnants to Downloads with `--quarantine`, or intentionally leave them ignored.
- [ ] Run **on the actual Mac**: `make lint && make test && make build`. Record pass/fail accurately. Run `make e2e` when Playwright browsers are installed; investigate failures before describing CI as passing.
- [ ] Verify OBS Virtual Camera preview, AI inference and explicit start/stop. Disconnect OBS, reconnect, and verify stale hints disappear and the camera can be released.
- [ ] Compare actual matched video frames to manual person counts; report the number of annotated frames, MAE and major failures. If not performed, mark accuracy *not yet measured*.
- [ ] Check names of metrics: current frame people vs selected-area estimate vs sustained peak vs shift average. These are not unique visits, customers, sales or exact wait times.
- [ ] Confirm that screenshots/video are yours to distribute and that the recording is labeled **"prerecorded café footage processed live through OBS"** where applicable.
- [ ] Review README, LICENSE/COPYING, [licensing](LICENSING.md), [café demo](CAFE_DEMO.md), and `.gitignore`; scan for hard-coded secrets and private paths.
- [ ] Confirm `git status`, staged files, the remote destination and GitHub Actions. Do not force push over old RoadPulse commits.
- [ ] Publish a public `v1.0.0` GitHub release **only after** the above steps pass or unverified aspects are clearly disclosed as limitations.

Passing the included tests only proves that selected software contracts hold. It does **not** certify café accuracy, customer classification, production security, or business ROI.

## Additional v1.1 acceptance checks

- [ ] Compare the three different time windows: **People visible now** (fresh frame), **Highest sustained count this shift** (median of nearby observations), and **Average visible this shift** (shift average).
- [ ] Pull OBS virtual camera while monitoring; confirm the current count becomes unavailable rather than showing an old value.
- [ ] Verify a human-labeled **seating** tile produces no low-motion service suggestion; compare an unlabeled and counter-labeled tile without interpreting either as a queue.
- [ ] Verify scene labels clear on view movement and via the clear control; they must not identify individuals.
- [ ] Run real, same-frame annotated count evaluation including at least clear and occluded frames if available. No accuracy claim before measuring. Follow [v1.1 validation](CAFE_V11_VALIDATION.md).
- [ ] Confirm the upgrade passes Mac `make lint && make test && make build`, and review GitHub Actions before tagging **v1.1.0**.
