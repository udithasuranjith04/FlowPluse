# FlowPulse AI — Café portfolio demo (about 90 seconds)

Use a fixed, permitted café video through **OBS Virtual Camera** or a consenting local camera. The OBS example is **prerecorded footage processed live**, not proof of a functioning commercial deployment. Do not show unauthorized faces/video in a publicly distributed recording.

1. **0–15 s — What it does.** Show the FlowPulse dashboard and say: "This is local-first computer vision that estimates visible people and summarizes activity from camera frames." Point out that the feed is a permitted demo, not a live café deployment.
2. **15–35 s — Live inference.** In **Live café**, show current confirmed person boxes, smoothly changing preview, visible-person count and the separate selected-area estimate. Note that boxes are sampled at AI FPS and may lag smooth video; amber dashed boxes are unverified last-seen hints and *not counted*.
3. **35–55 s — Actionable context.** Show the recent count trend and automatic scene hotspots. Explain that a seating-area low-motion hotspot is a *descriptive observation*, not a confirmed queue or slow service.
4. **55–70 s — Shift summary.** Explain current count, sustained high (five-nearby-frame median), and shift average. Do not describe a raw frame count as actual guests or sales.
5. **70–90 s — Engineering.** Open System health to show sampled inference FPS and source status. Mention FastAPI/Python, YOLO11n, OpenCV, React/TypeScript, anonymous session tracking, no cloud footage uploads by default, and limitations from occlusion and camera viewpoint.

## Publish alongside the demo

- A screenshot cropped to FlowPulse only (not private browser tabs/OBS settings).
- Architecture diagram from `docs/ARCHITECTURE.md`.
- Actual Mac results from `make lint && make test && make build`, and any real annotated-data accuracy metrics.
- Camera and sample footage attribution/permission where relevant, and an honest limitations section.

**Avoid:** claims of verified distinct customer counts, real waiting time, near-perfect accuracy, automatic staff recognition, emotion detection, or 24/7 production reliability.
