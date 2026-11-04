import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { SceneDiscoveryPanel } from "../src/SceneDiscoveryPanel";
import type { Status } from "../src/types";

it("overlays automatic hotspots on a real camera reference without owner geometry", () => {
  render(<SceneDiscoveryPanel status={{
    camera_id: "local-camera-1", frame_id: "test-id", resolution: [1280, 720],
    ai_state: "active", state: "LIVE", detection_target: "person", preview_only: false,
    automatic_insights: { scene_discovery: {
      state: "ready", sampled_frames: 80, window_seconds: 40, disclaimer: "Test",
      hotspots: [{ id: "scene-2-3", bounds: [0.5, 0.5, 0.6667, 0.75], location: "Lower right", pattern: "movement", evidence: "strong", frames_with_people: 60, visible_now: 1, presence_share: 0.4 }],
    } },
  } as unknown as Status}/>);
  const map = screen.getByRole("img", { name: /Camera view activity map/ });
  expect(map.querySelector("img")?.getAttribute("src")).toContain("overlays=false");
  expect(map.querySelector(".scene-hotspot")).not.toBeNull();
  expect(screen.getByText(/Movement activity/)).toBeInTheDocument();
});
