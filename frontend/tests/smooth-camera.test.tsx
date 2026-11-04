import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { LivePreview } from "../src/App";
import type { Status } from "../src/types";

const base = {
  camera_id: "local-camera-0", control_revision: 123, mode: "LIVE", state: "LIVE",
  ai_state: "active", preview_only: false, detection_target: "person",
  frame_id: "frame-one", resolution: [1280, 720], processed_fps: 2, preview_fps: 12,
  processed_frame_age_seconds: 0.3, continuous_frames_verified: true,
  tracks: [{ id: "temporary-1", label: "person", confidence: 0.92,
    box: [0.2, 0.2, 0.4, 0.6], image_plane_motion_per_second: 0 }],
} as unknown as Status;

it("keeps a single camera image as AI frame IDs and overlays change", () => {
  const ui = render(<LivePreview status={base} />);
  const streamImage = screen.getByRole("img", { name: /Live person-detection camera/ });
  expect(streamImage.getAttribute("src")).toContain("/api/stream/local-preview.mjpg?");
  expect(streamImage.getAttribute("src")).not.toContain("frame_id=");
  expect(screen.getByLabelText(/Latest sampled AI detection boxes/)).toBeInTheDocument();

  ui.rerender(<LivePreview status={{ ...base, frame_id: "frame-two" }} />);
  expect(screen.getByRole("img", { name: /Live person-detection camera/ })).toBe(streamImage);
  fireEvent.click(screen.getByRole("button", { name: /Overlays/ }));
  expect(screen.getByRole("img", { name: /Live person-detection camera/ })).toBe(streamImage);
  expect(screen.queryByLabelText(/Latest sampled AI detection boxes/)).toBeNull();
  expect(screen.getByText(/Video 12.0 FPS · AI 2.0 FPS/)).toBeInTheDocument();
});

it("replaces the MJPEG image when the camera source revision changes", () => {
  const ui = render(<LivePreview status={base} />);
  const first = screen.getByRole("img", { name: /Live person-detection camera/ });
  ui.rerender(<LivePreview status={{ ...base, control_revision: 124 }} />);
  expect(screen.getByRole("img", { name: /Live person-detection camera/ })).not.toBe(first);
});

it("does not render a stale person box after the model misses that person", () => {
  const status = {
    ...base, frame_id: "new-sample", detector_input_size: 960,
    tracks: [], visible_people: 0,
    overlay_tracks: [
      { id: "anonymous:1", confidence: 0.42, box: [0.2, 0.2, 0.4, 0.6], held: true },
    ],
  } as Status;
  const ui = render(<LivePreview status={status} />);
  const image = screen.getByRole("img", { name: /Live person-detection camera/ });
  expect(screen.queryByLabelText(/Latest sampled AI detection boxes/)).toBeNull();
  expect(screen.getByText(/Detail 960px/)).toBeInTheDocument();
  ui.rerender(<LivePreview status={{ ...status, overlay_tracks: [] }} />);
  expect(screen.queryByLabelText(/Latest sampled AI detection boxes/)).toBeNull();
  expect(screen.getByRole("img", { name: /Live person-detection camera/ })).toBe(image);
});


it("reports current focused-scan mode without changing the camera connection", () => {
  const status = { ...base, detail_scan_mode: "scanning" as const };
  render(<LivePreview status={status} />);
  expect(screen.getByText(/Close-up scans on/)).toBeInTheDocument();
  expect(screen.getByLabelText(/Latest sampled AI detection boxes/)).toBeInTheDocument();
});


it("shows a brief unverified dashed hint for one missed sample, not a current person", () => {
  const missed = {
    ...base, frame_id: "new-sample", visible_people: 0, tracks: [],
    processed_frame_age_seconds: 0.2,
    overlay_tracks: [{
      id: "anonymous:1", confidence: 0.91, box: [0.2, 0.2, 0.4, 0.6],
      held: true, held_age_seconds: 0.5,
    }],
  } as Status;
  const ui = render(<LivePreview status={missed} />);
  expect(screen.getByLabelText(/Latest sampled AI detection boxes/)).toBeInTheDocument();
  expect(screen.getByText("last seen · not verified")).toBeInTheDocument();
  expect(document.querySelector(".stage-ai-boxes rect")?.getAttribute("stroke-dasharray")).toBe("10 7");
  ui.rerender(<LivePreview status={{ ...missed, processed_frame_age_seconds: 1.1 }} />);
  expect(screen.queryByText("last seen · not verified")).toBeNull();
});
