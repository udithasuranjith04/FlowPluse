import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { SimpleInsights } from "../src/SimpleInsights";

it("shows real live person counts and an in-memory history without spatial setup", () => {
  const advanced = vi.fn();
  render(<SimpleInsights onAdvanced={advanced} onZones={() => {}} status={{
    ai_state: "active", detection_target: "person", preview_only: false,
    visible_people: 3, processed_fps: 2, tracks: [
      { id: "a", label: "person", confidence: 0.85, box: [0, 0, 1, 1], image_plane_motion_per_second: 0 },
    ], people_count_history: [
      { at: "2026-11-02T10:00:00Z", people: 1 },
      { at: "2026-11-02T10:00:01Z", people: 3 },
    ],
  }} />);
  expect(screen.getByText("Café service pulse")).toBeInTheDocument();
  expect(screen.getByText("Latest 3")).toBeInTheDocument();
  expect(screen.getByRole("img", { name: /Count trend from 2 frames/ })).toBeInTheDocument();
  expect(screen.getByText("Anonymous tracks")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /View shift summary/ }));
  expect(advanced).toHaveBeenCalledOnce();
});

it("does not invent counts while camera is unavailable", () => {
  render(<SimpleInsights onAdvanced={() => {}} onZones={() => {}} status={{ ai_state: "paused", processed_fps: 0, visible_people: 12, detection_target: "person" }} />);
  expect(screen.getByText("Connect your camera to see actual guest activity.")).toBeInTheDocument();
  expect(screen.queryByText("12")).not.toBeInTheDocument();
});
