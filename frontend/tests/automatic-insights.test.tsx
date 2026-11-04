import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { SimpleInsights } from "../src/SimpleInsights";
import type { Status } from "../src/types";

it("shows automatic image statistics but never presents crossings as physical entrances", () => {
  const status = {
    ai_state: "active", detection_target: "person", processed_fps: 2,
    preview_only: false, visible_people: 4, tracks: [], people_count_history: [],
    automatic_insights: {
      sample_count: 30, average_visible: 3.7, peak_visible: 8,
      visible_trend: "rising", busiest_image_sector: "bottom left", sector_share: 0.4,
      image_midline_crossings: { left_to_right: 2, right_to_left: 1 }, limitations: "Image-plane only",
    },
  } as const;
  render(<SimpleInsights status={status as unknown as Status} onAdvanced={() => {}} onZones={() => {}} />);
  expect(screen.getByText("Service snapshot")).toBeInTheDocument();
  expect(screen.getByText("Activity level")).toBeInTheDocument();
  expect(screen.getByText("bottom left")).toBeInTheDocument();
  expect(
  screen.getByText(/not exact queue length, and not certified occupancy/i),
).toBeInTheDocument();
  expect(screen.queryByText("2 entries")).not.toBeInTheDocument();
});
