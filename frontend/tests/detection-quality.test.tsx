import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { LivePreview, heldBoxOpacity, sampledBoxOpacity } from "../src/App";
import { CafeShift } from "../src/CafeShift";
import type { Status } from "../src/types";

it("expires sampled boxes rather than presenting an old position as live tracking", () => {
  expect(sampledBoxOpacity(0.1)).toBeGreaterThan(0.9);
  expect(sampledBoxOpacity(0.6)).toBeGreaterThan(0);
  expect(sampledBoxOpacity(0.6)).toBeLessThan(0.9);
  expect(sampledBoxOpacity(0.9)).toBeGreaterThan(0);
  expect(sampledBoxOpacity(1.1)).toBe(0);
  expect(sampledBoxOpacity(0.9, 2, 550)).toBeGreaterThan(0);
  expect(sampledBoxOpacity(2.0, 0.7, 600)).toBe(0);
  expect(sampledBoxOpacity(Number.NaN)).toBe(0);
  expect(heldBoxOpacity(0.2, 0.5)).toBeGreaterThan(0);
  expect(heldBoxOpacity(0.8, 0.5)).toBe(0);
});

it("keeps smooth MJPEG video while hiding overly old detection coordinates", () => {
  const stale = {
    camera_id: "local-camera-0", control_revision: 321,
    detection_target: "person", ai_state: "active", state: "LIVE", mode: "LIVE",
    preview_only: false, continuous_frames_verified: true, frame_id: "one",
    resolution: [1280, 720], processed_frame_age_seconds: 1.6,
    overlay_tracks: [{ id: "temporary", box: [0.1, 0.2, 0.3, 0.7], confidence: 0.92, held: false }],
  } as unknown as Status;
  render(<LivePreview status={stale} />);
  expect(screen.getByRole("img", { name: /Live person-detection camera/ }).getAttribute("src"))
    .toContain("local-preview.mjpg");
  expect(screen.queryByLabelText("Latest sampled AI detection boxes")).toBeNull();
});

it("uses sustained high counts for the owner while exposing raw spikes honestly", () => {
  const status = {
    ai_state: "active", detection_target: "person", preview_only: false,
    automatic_insights: { session_summary: {
      processed_samples: 100, elapsed_seconds: 60,
      average_visible: 4.5, peak_visible: 19, supported_peak_visible: 6,
      peak_possible_outlier: true, peak_support_window: 5,
      busy_sample_percent: 20, minute_averages: [{ minute: 0, average: 4.5 }],
    } },
  } as unknown as Status;
  render(<CafeShift status={status} onCamera={() => {}} />);
  expect(screen.getByText("Sustained high count")).toBeInTheDocument();
  expect(screen.getByText("6")).toBeInTheDocument();
  expect(screen.getByText(/Raw single-frame maximum: 19/)).toBeInTheDocument();
  expect(screen.getByText(/duplicate or false detection/)).toBeInTheDocument();
});
