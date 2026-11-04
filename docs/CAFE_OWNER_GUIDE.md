# FlowPulse Café Edition — owner guide

FlowPulse is a privacy-conscious research prototype for small cafés and restaurants. It helps a manager observe how many **people are visible to one camera**, whether that visible activity is changing, and whether configured service-area signals deserve human review. **It does not identify customers, detect purchases, measure actual service time, infer table turns, or certify occupancy.** A person visible in the scene might be staff rather than a guest.

## Simple setup (no geometric configuration)

1. Start the app with `make dev` and open its local dashboard.
2. Select **Camera setup**, choose your own authorized Mac or iPhone Continuity Camera, and confirm local-analysis consent and participant notice.
3. Preview the scene. Keep the camera fixed and check that the area you want to observe is visible and changing frames are verified.
4. Select **Start monitoring**. No polygon drawing, model threshold tuning, cloud account, or paid API is required to see automatic counts, image-center crossings, longest visible-track age, activity bands, and session trend information.
5. Open **Live café** for current visible counts, activity level, track-age estimates, the live view, and suggestions for what to check in person.
6. Open **Shift summary** for a session-only mean and peak of detected people, busy-frame share, and minute-by-minute history. All of this comes from processed frames; none is invented from camera capacity or assumed sales data.
7. Open **Service alerts** for measured attention signals. Historical rule observations remain under System health. These require an appropriate confirmed waiting zone. New users can ignore the optional expert geometry tools.
8. Use **System health** if monitoring isn't working. Its advanced details are intentionally collapsed.

## What is automated?

- The person detector, bounded temporary tracking, present count, recent trend, image-sector distribution, and midline motion signals are automatic after a permitted source starts.
- Longest/average visible-track ages are computed for currently present anonymous tracks. They are **not** a person's total time in the café, service duration, or waiting time; tracks can be lost/restarted and occluded people are missed.
- Current activity tiers are **fixed illustrative thresholds**, not an AI-certified crowd or staffing assessment. Labels reflect visible people only: `quiet` (<3), `steady` (3–6), `busy` (7–11), `rush` (12+). The operator prompt is a rule-based suggestion, not a prediction about what staff must do.
- Shift numbers summarize **only healthy frames processed while monitoring** and live only in process memory. Preview frames are excluded. Shift data resets on stop/source change; no persisted daily history or video is created.
- The minute plot retains at most 720 per-minute aggregates while the live session's overall average and peak remain accurate for the current run.

## What still needs a real boundary?

**Door entries/exits and reliable counter queue measurement cannot be inferred from an arbitrary camera view.** A café entrance may be out of frame and people near a counter are not always queuing. The old manual zone/line editor remains under **Camera setup → Optional expert tools** for installations that need specific geometric interpretations. Never present the automatic image-midline left/right movements as actual doorway visits.

## Privacy, calibration, and release

Obtain permission to film, post notice to participants and keep the device local. No facial recognition or persistent person IDs. Check the camera view for staff, mirrors, occlusions, source interruptions and changing light. Evaluate with consenting participants and known ground-truth counts before pitching claims of accuracy. The existing `make evaluate-counts FILE=...` can evaluate annotated frame counts; use `docs/RELEASE_CHECKLIST.md` for broader acceptance checks.

## Developer verification

From the repository root: `make lint`, `make test`, `make build`, then `make dev`. The tests verify logic and basic UI contracts, not Mac camera permissions, model accuracy, camera reconnects, or real-world queue performance.
