import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { SceneDiscoveryPanel } from "../src/SceneDiscoveryPanel";
import type { Status } from "../src/types";

it("automatically explains a learned activity region without role classification", () => {
  const status = {
    detection_target: "person", ai_state: "active", preview_only: false, state: "LIVE",
    automatic_insights: {
      scene_discovery: {
        state: "ready", sampled_frames: 80, window_seconds: 40,
        hotspots: [{ id: "scene-2-3", bounds: [0.5, 0.5, 0.6667, 0.75], location: "Lower middle center-right", pattern: "longer_stays", evidence: "strong", frames_with_people: 60, visible_now: 2, presence_share: 0.4 }],
        disclaimer: "No identity inference",
      },
    },
  } as Status;
  render(<SceneDiscoveryPanel status={status}/>);
  expect(screen.getByText("Where is activity happening?")).toBeInTheDocument();
  expect(screen.getByText(/Sustained low movement/)).toBeInTheDocument();
  expect(screen.getByText(/60 sampled frames/)).toBeInTheDocument();
  expect(screen.getByText(/not automatic staff\/customer recognition/)).toBeInTheDocument();
  expect(screen.queryByText(/identified staff/i)).not.toBeInTheDocument();
});

it("does not pretend to discover areas from preview or missing camera data", () => {
  const status = {
    detection_target: "person", ai_state: "active", preview_only: true, state: "LIVE",
    automatic_insights: { scene_discovery: { state: "ready", sampled_frames: 100, window_seconds: 50, hotspots: [], disclaimer: "" } },
  } as unknown as Status;
  render(<SceneDiscoveryPanel status={status}/>);
  expect(screen.getByText("Automatic discovery starts with monitoring")).toBeInTheDocument();
  expect(screen.getByText(/Preview alone never builds activity profiles/)).toBeInTheDocument();
});

it("shows scene activity as information, not an urgent staff or queue alert", async () => {
  const { deriveServiceSignals } = await import("../src/ServiceAlerts");
  const status = {
    camera_id: "local-camera-1", detection_target: "person", ai_state: "active", state: "LIVE",
    continuous_frames_verified: true, quality_flags: [], processed_frame_age_seconds: 0.2,
    automatic_insights: {
      scene_discovery: {
        state: "ready", sampled_frames: 70, window_seconds: 50,
        hotspots: [{ id: "scene-2-2", bounds: [0.3, 0.5, 0.5, 0.75], location: "Lower middle left", pattern: "longer_stays", evidence: "strong", frames_with_people: 50, visible_now: 1, presence_share: 0.4 }],
      },
    },
  } as unknown as Status;
  const signals = deriveServiceSignals(status);
  expect(signals.some((s) => s.id === "scene-stays-scene-2-2" && s.level === "info")).toBe(true);
  expect(signals.every((s) => s.level !== "attention")).toBe(true);
});


it("withholds learned hotspots after camera motion until monitoring restarts", () => {
  const status = {
    camera_id: "local-camera-1", state: "LIVE", ai_state: "active", detection_target: "person", view_shift_detected: true,
    automatic_insights: { scene_discovery: {
      state: "ready", sampled_frames: 140, window_seconds: 70, disclaimer: "",
      hotspots: [{ id: "a", bounds: [0, 0, 0.2, 0.2], location: "top left", pattern: "longer_stays", evidence: "strong", frames_with_people: 130, visible_now: 1, presence_share: 0.5 }],
    } },
  } as unknown as Status;
  render(<SceneDiscoveryPanel status={status}/>);
  expect(screen.getByText("Camera view changed")).toBeInTheDocument();
  expect(screen.queryByText("Sustained low movement")).not.toBeInTheDocument();
  expect(screen.getByText(/restart to learn one consistent view/i)).toBeInTheDocument();
});
