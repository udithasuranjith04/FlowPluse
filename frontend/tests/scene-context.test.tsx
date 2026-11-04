import { fireEvent, render, screen, cleanup } from "@testing-library/react";
import { afterEach, beforeEach, expect, it } from "vitest";
import { SceneDiscoveryPanel } from "../src/SceneDiscoveryPanel";
import { deriveServiceSignals } from "../src/ServiceAlerts";
import { clearSceneTags, readSceneTags, sceneAreaGuidance, writeSceneTag } from "../src/sceneContext";
import type { Status } from "../src/types";

const camera = "local-camera-1";
function activeScene(): Status {
  return {
    camera_id: camera, detection_target: "person", ai_state: "active", state: "LIVE",
    preview_only: false, processed_frame_age_seconds: 0.1, continuous_frames_verified: true,
    quality_flags: [],
    automatic_insights: { scene_discovery: {
      state: "ready", sampled_frames: 80, window_seconds: 40, disclaimer: "",
      hotspots: [{ id: "scene-2-3", bounds: [0.5, 0.5, 0.6667, 0.75], location: "Lower middle center-right", pattern: "longer_stays", evidence: "strong", frames_with_people: 64, visible_now: 1, presence_share: 0.4 }],
    } },
  } as unknown as Status;
}

beforeEach(() => localStorage.clear());
afterEach(() => { cleanup(); localStorage.clear(); });

it("stores only bounded, operator-selected labels per camera", () => {
  expect(readSceneTags(camera)).toEqual({});
  expect(writeSceneTag(camera, "scene-2-3", "seating")).toEqual({ "scene-2-3": "seating" });
  expect(readSceneTags(camera)).toEqual({ "scene-2-3": "seating" });
  expect(readSceneTags("local-camera-2")).toEqual({});
  expect(writeSceneTag(camera, "../../sensitive", "counter")).toEqual({});
  expect(readSceneTags(camera)).toEqual({ "scene-2-3": "seating" });
  clearSceneTags(camera);
  expect(readSceneTags(camera)).toEqual({});
});

it("supports contextual labels without converting seating into a service warning", () => {
  const status = activeScene();
  render(<SceneDiscoveryPanel status={status}/>);
  fireEvent.change(screen.getByLabelText("What is this part of your café?"), { target: { value: "seating" } });
  expect(screen.getByText(/Owner-labeled seating: low movement is expected/)).toBeInTheDocument();
  expect(deriveServiceSignals(status).some((signal) => signal.id.startsWith("scene-stays-"))).toBe(false);
  expect(deriveServiceSignals(status).some((signal) => signal.level === "attention")).toBe(false);
  expect(sceneAreaGuidance("counter", "longer_stays")).toMatch(/does not establish a queue/);
  fireEvent.click(screen.getByRole("button", { name: "Clear my area labels" }));
  expect(readSceneTags(camera)).toEqual({});
});

it("invalidates stored area labels when camera movement is detected", () => {
  writeSceneTag(camera, "scene-2-3", "counter");
  const status = activeScene();
  const { rerender } = render(<SceneDiscoveryPanel status={status}/>);
  expect(screen.getByDisplayValue("Counter / pickup area")).toBeInTheDocument();
  rerender(<SceneDiscoveryPanel status={{ ...status, view_shift_detected: true }}/>);
  expect(screen.getByText("Camera view changed")).toBeInTheDocument();
  expect(readSceneTags(camera)).toEqual({});
  rerender(<SceneDiscoveryPanel status={{ ...status, view_shift_detected: false }}/>);
  expect(screen.getByDisplayValue("Unlabeled camera area")).toBeInTheDocument();
});
