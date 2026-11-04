import { expect, it } from "vitest";
import { currentCountTrusted } from "../src/App";
import type { Status } from "../src/types";

function healthyStatus(): Status {
  return {
    camera_id: "local-camera-0", state: "LIVE", ai_state: "active",
    detection_target: "person", preview_only: false,
    continuous_frames_verified: true, processed_frame_age_seconds: 0.3,
    last_error: null, quality_flags: [],
  } as unknown as Status;
}

it("shows current counts only for recent verified person frames", () => {
  expect(currentCountTrusted(healthyStatus())).toBe(true);
  expect(currentCountTrusted(null)).toBe(false);
  expect(currentCountTrusted({ ...healthyStatus(), processed_frame_age_seconds: 3.1 })).toBe(false);
  expect(currentCountTrusted({ ...healthyStatus(), processed_frame_age_seconds: Number.NaN })).toBe(false);
  expect(currentCountTrusted({ ...healthyStatus(), continuous_frames_verified: false })).toBe(false);
  expect(currentCountTrusted({ ...healthyStatus(), quality_flags: ["camera_view_moving"] })).toBe(false);
  expect(currentCountTrusted({ ...healthyStatus(), last_error: "Camera disconnected" })).toBe(false);
  expect(currentCountTrusted({ ...healthyStatus(), preview_only: true })).toBe(false);
  expect(currentCountTrusted({ ...healthyStatus(), view_shift_detected: true })).toBe(false);
  expect(currentCountTrusted({ ...healthyStatus(), state: "PAUSED" })).toBe(false);
  expect(currentCountTrusted({ ...healthyStatus(), camera_id: "demo" })).toBe(false);
});
