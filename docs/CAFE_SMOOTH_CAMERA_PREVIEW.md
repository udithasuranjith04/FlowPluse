# Smooth local camera display (FlowPulse Café)

**Purpose:** Keep a locally authorized camera preview visually responsive while person analytics continue at their independently configured inference rate.

## How it works

- Capture is still handled by the selected local AVFoundation camera. The capture worker publishes **at most 15 compressed JPEG preview frames per second** to one latest-frame memory slot. Frames are never added to a growing queue or stored on disk.
- `GET /api/stream/local-preview.mjpg?camera_id=local-camera-N` provides an MJPEG stream for the **currently selected local camera only**. The connection ends on camera/source change or stop. Browser caching is disabled.
- Live Café mounts **one persistent image** for this stream. It does not create an image element for every AI frame. The camera image can update faster than YOLO.
- The newest anonymous person-tracker bounding boxes are drawn separately using SVG. They update at the normal **AI status sampling rate**, not on each camera preview frame. They are indicative, not frame-perfect annotations on the displayed video.
- Toggle Overlays without restarting the stream. Shift counts, detections, alerts, camera quality and Automatic Scene Intelligence continue using the original processed AI frames. Snapshot/replay and paused views retain the existing frame-based display path.

## Performance, privacy and safety

- The target of up to 15 FPS is a display cap, **not** guaranteed performance or a change to the YOLO inference rate. Live Café reports the measured camera-preview and AI processing rates separately. The source camera, computer, browser and network must keep up.
- Raw camera data is not persisted; at most one additional compressed preview frame is held in process memory. Opening the local camera still requires explicit user consent.
- Current source identification and capture-generation checks prevent a previously selected camera's frames from being published into the next session. A frozen stream is not represented as current live video.
- On any rendering problem, inspect **System health** and try the "Reconnect preview" control before changing the AI settings. If the video remains slow, check OBS Virtual Camera's output resolution and CPU usage.

For a public demo using an externally sourced café clip, obtain necessary reuse permission and clearly label the footage as prerecorded. Live analysis of a prerecorded clip is not live café monitoring.
