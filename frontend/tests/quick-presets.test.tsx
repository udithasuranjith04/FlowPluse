import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import ZoneEditor from "../src/ZoneEditor";
import type { Camera, ZoneConfig } from "../src/types";

const camera = { id: "local-camera-1", name: "Local" } as Camera;
const config: ZoneConfig = {
  zones: [], lines: [], rules: {
    stationary_seconds: 12, min_track_age: 8, motion_threshold: 0.005,
    occupancy_threshold: 0.16, occupancy_increase: 0.08, baseline_window: 20,
    congestion_seconds: 20, cooldown_seconds: 60, min_confidence: 0.35, target_fps: 2,
  },
};
afterEach(() => vi.restoreAllMocks());

it("saves a whole-frame zone through the existing API without removing existing rules", async () => {
  const sent: ZoneConfig[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (_url, options) => {
    if (options?.method === "PUT") sent.push(JSON.parse(String(options.body)) as ZoneConfig);
    return { ok: true, json: async () => sent.at(-1) ?? config } as Response;
  });
  render(<ZoneEditor camera={camera} onSave={() => {}} people />);
  fireEvent.click(await screen.findByRole("button", { name: "Use dining floor" }));
  await waitFor(() => expect(sent).toHaveLength(1));
  expect(sent[0].zones[0].points).toEqual([[0.01, 0.01], [0.99, 0.01], [0.99, 0.99], [0.01, 0.99]]);
  expect(sent[0].rules.min_confidence).toBe(0.35);
  expect(
  await screen.findByText(/Full-frame count-only zone saved/)
).toBeInTheDocument();
});

it("adds a directed starter line and can reverse its orientation", async () => {
  const sent: ZoneConfig[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (_url, options) => {
    if (options?.method === "PUT") sent.push(JSON.parse(String(options.body)) as ZoneConfig);
    return { ok: true, json: async () => sent.at(-1) ?? config } as Response;
  });
  render(<ZoneEditor camera={camera} onSave={() => {}} people />);
  fireEvent.click(await screen.findByRole("button", { name: "Add starter entry line" }));
  await waitFor(() => expect(sent).toHaveLength(1));
  expect(sent[0].lines?.[0].points).toEqual([[0.15, 0.5], [0.85, 0.5]]);
  fireEvent.click(await screen.findByRole("button", { name: /Reverse counting line Starter entrance line/ }));
  fireEvent.click(screen.getByRole("button", { name: "Save configuration" }));
  await waitFor(() => expect(sent).toHaveLength(2));
  expect(sent[1].lines?.[0].points).toEqual([[0.85, 0.5], [0.15, 0.5]]);
});
