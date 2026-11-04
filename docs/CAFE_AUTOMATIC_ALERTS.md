# FlowPulse Café — Automatic service alerts and shift insights

## What changed for café owners

- **Live café:** One people-visible count, a recent *direction* indicator (rising/steady/calmer), a peak count, live camera and a short recent chart. Counts are camera-view estimates, not customer visits. We removed duplicated metric cards.
- **Service alerts:** The main owner navigation no longer displays a manual observation review inbox. It shows *current actionable conditions*: a camera problem, sustained increase in visible people relative to earlier healthy frames in **the same session**, and a possible-queue observation only from a properly configured non-starter area. All calculation and display work automatically after camera consent and monitoring.
- **Optional browser desktop notifications:** Off by default, require a button click and browser permission. Work only while the web app is open. No push provider or external service. The same active condition is notified once per camera session.
- **Shift summary:** Instead of a one-size-fits-all threshold ("7 people = busy"), the primary dashboard says **Learning** until at least four minute buckets exist, then compares the first two and latest two buckets. It offers local CSV export of minute-average counts. Its technical automatic image-plane detail is accessible in a collapsed section.
- **History and manual review:** Prior observations, including incorrect starter-zone events, remain preserved. The historical archive and CSV export live under **System health → Historical observation archive**. Café owners do not need to acknowledge every alert.

## What the AI can and cannot infer

Without manually drawing zones, it can detect visible people, approximate movement and changes, and monitor frame health. A stationary, permitted camera is necessary for meaningful comparisons. It **cannot** learn a real café entrance, dining vs ordering areas, exact waiting time, number of customers served, customer purchases, or staff needs with dependable precision from every camera angle.

An unadjusted *Starter waiting area · adjust location* template now acts as count-only and does not create new dwell or queue events. Adjust the polygon and rename it in **Camera setup → Optional expert tools** before using it for location-specific queue hypotheses. Historical events are not deleted.

The alert algorithm requires **at least 32 healthy recent processed frames** and a sustained increase; it does not issue a rush alert for a one-frame spike. This is an *intra-session comparison*—not a historical learned business baseline. With 2 processed FPS, it needs around 16 seconds to accumulate 32 samples, and the comparison windows cover only part of that recent history.

The shift dashboard is **current-session only** and resets when the camera stops or the source changes. CSV export is an operator action and includes only minute-level mean people-visible counts, no identities, track IDs or raw frames.

## First-run and acceptance checks on your Mac

1. Start the backend and frontend using `make dev`; do not auto-start the camera.
2. Check **Service alerts** before starting: the page should indicate monitoring is inactive without inventing queue pressure.
3. Approve camera access, preview a permitted fixed scene, and click **Start monitoring**. No preview measurements should be added to the shift report.
4. Confirm the Live Café page shows exactly three primary metrics and one recent activity chart; verify **Service alerts** updates from fresh status messages.
5. With a controlled scene, test a normal stable period, one-frame person-count spike (must not alert), and a sustained relative count increase (may alert after sufficient frames). Verify the text doesn't describe these as definite customer queues.
6. Confirm an unadjusted starter waiting zone does not create new dwell/queue events; previously stored events remain in the archive.
7. Click **Enable notifications** and grant browser permission on localhost. Check that an active attention signal generates one desktop notification; denied/unavailable browsers should still show on-screen signals.
8. Allow several minutes of monitored activity to accumulate, check shift time labels, export CSV, and verify it contains no personal data. Stop or change cameras and confirm session shift resets.
9. Run `make lint`, `make test`, `make build`, and `make verify-people` on your Apple Silicon Mac. Test multiple start/stop/preview cycles.

## Design/research considerations

Retail people-counting guidance repeatedly identifies occlusion, reflections, viewpoint, and unpredictable tracking in crowded scenes as sources of errors. Those limitations matter for café queues; one generic view is not reliable proof of queue length or customer wait time.

References:
- [Milestone BriefCam people-counting best practices](https://doc.milestonesys.com/briefcam/briefcam-white-papers/2024r2/en/people-counting-best-practices)
- [Verkada occupancy trends guide](https://docs.verkada.com/docs/occupancy-trends-guide.pdf)

FlowPulse Café Edition remains an evaluation prototype, not a certified business metric or safety system. Keep authorized camera and participant notice requirements.
