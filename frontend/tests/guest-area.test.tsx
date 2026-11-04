import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { GuestAreaSetup } from "../src/GuestAreaSetup";
import type { Camera, ZoneConfig } from "../src/types";

const camera = { id: "local-camera-1", name: "Permitted camera" } as Camera;
const config: ZoneConfig = { staff_only_region: "none", zones: [
  { id: "existing", name: "Confirmed counter", kind: "monitoring_lane", points: [[0, 0], [0.6, 0], [0.6, 0.6]] },
], lines: [], rules: {
  stationary_seconds: 12,
  min_track_age: 8,
  motion_threshold: 0.005,
  occupancy_threshold: 0.16,
  occupancy_increase: 0.08,
  baseline_window: 20,
  congestion_seconds: 20,
  cooldown_seconds: 60,
  min_confidence: 0.35,
  target_fps: 2,
} };
afterEach(() => { vi.restoreAllMocks(); });

it("keeps the camera private and retains expert geometry when saving the staff-only half", async () => {
  let saved: ZoneConfig | undefined;
  const onSave = vi.fn();
  const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation(async (_url, init) => {
    if (init?.method === "PUT") saved = JSON.parse(String(init.body)) as ZoneConfig;
    return { ok: true, json: async () => saved ?? config } as Response;
  });
  render(<GuestAreaSetup camera={camera} onSave={onSave} />);
  const selection = await screen.findByLabelText("Which half is mostly staff-only?");
  expect(screen.getByRole("button", { name: /Save camera area/ })).toBeDisabled();
  fireEvent.change(selection, { target: { value: "left" } });
  expect(screen.getByText(/STAFF-ONLY SIDE/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /Save camera area/ }));
  await waitFor(() => expect(onSave).toHaveBeenCalledOnce());
  expect(saved?.staff_only_region).toBe("left");
  expect(saved?.zones).toEqual(config.zones);
  expect(saved?.rules.min_confidence).toBe(0.35);
  expect(fetchSpy.mock.calls.every(([url]) => String(url).includes("/zones"))).toBe(true);
  expect(screen.getByText(/not automatic staff recognition/i)).toBeInTheDocument();
});
