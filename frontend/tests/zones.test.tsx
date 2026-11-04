import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import ZoneEditor from "../src/ZoneEditor";
import type { Camera } from "../src/types";
const camera = { id: "demo", name: "Demo" } as Camera;
const config = {
  zones: [],
  rules: {
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
  },
};
it("supports keyboard-accessible coordinates and persists a polygon", async () => {
  const fetchMock = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValue({ ok: true, json: async () => config } as Response);
  render(<ZoneEditor camera={camera} onSave={() => {}} />);
  await screen.findByLabelText("Zone name");
  for (const [x, y] of [
    [0.1, 0.1],
    [0.8, 0.1],
    [0.8, 0.8],
  ]) {
    fireEvent.change(screen.getByLabelText("X"), { target: { value: x } });
    fireEvent.change(screen.getByLabelText("Y"), { target: { value: y } });
    fireEvent.click(screen.getByRole("button", { name: "Add point" }));
  }
  fireEvent.click(screen.getByRole("button", { name: "Add polygon" }));
  fireEvent.click(screen.getByRole("button", { name: "Save configuration" }));
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
  const init = fetchMock.mock.calls[1][1];
  expect(init?.method).toBe("PUT");
  expect(JSON.parse(String(init?.body)).zones[0].points).toEqual([
    [0.1, 0.1],
    [0.8, 0.1],
    [0.8, 0.8],
  ]);
  expect(await screen.findByText(/Configuration saved/)).toBeInTheDocument();
  fetchMock.mockRestore();
});
