import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { CafeShift, shiftDirection } from "../src/CafeShift";
import type { Status } from "../src/types";

it("shows real session-only counts, not made-up visits or historic sales", () => {
  const onCamera = vi.fn();
  const status = {
    ai_state: "active", detection_target: "person",
    automatic_insights: {
      session_summary: {
        processed_samples: 80, average_visible: 4.5, peak_visible: 12,
        busy_sample_percent: 40, elapsed_seconds: 120,
        minute_averages: [{ minute: 0, average: 3 }, { minute: 1, average: 6 }],
      },
    },
  } as Status;
  render(<CafeShift status={status} onCamera={onCamera} />);
  expect(screen.getByText("What did your camera see this shift?")).toBeInTheDocument();
  expect(screen.getByText("4.5")).toBeInTheDocument();
  expect(screen.getByText("12")).toBeInTheDocument();
  expect(screen.getAllByText("Learning").length).toBeGreaterThan(0);
  expect(screen.getByRole("img", { name: /across 2 session minutes/ })).toBeInTheDocument();
  expect(screen.getByText(/not an all-day business report/i)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Export CSV" })).toHaveAttribute("download", "flowpulse-shift-minutes.csv");
  fireEvent.click(screen.getByRole("button", { name: "Review camera setup" }));
  expect(onCamera).toHaveBeenCalledOnce();
});

it("does not invent shift statistics while the camera is unavailable", () => {
  const onCamera = vi.fn();
  render(<CafeShift status={null} onCamera={onCamera} />);
  expect(screen.getByText("Start monitoring to collect real shift data.")).toBeInTheDocument();
  expect(screen.queryByText("4.5")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Connect camera" }));
  expect(onCamera).toHaveBeenCalledOnce();
});


it("labels comparisons as learning until enough session minutes exist", () => {
  expect(shiftDirection([{minute:0, average:2}, {minute:1, average:6}]).label).toBe("Learning");
  expect(shiftDirection([{minute:0, average:1}, {minute:1, average:2}, {minute:2, average:6}, {minute:3, average:7}]).label).toBe("Busier");
  expect(shiftDirection([{minute:0, average:7}, {minute:1, average:6}, {minute:2, average:2}, {minute:3, average:1}]).label).toBe("Calmer");
});


it("distinguishes estimated guest-facing-area activity from overall camera counts", () => {
  const status = {
    ai_state: "active", detection_target: "person", staff_only_region: "top",
    automatic_insights: { session_summary: {
      processed_samples: 40, average_visible: 6.5, peak_visible: 10,
      guest_area_average: 3.2, guest_area_peak: 5,
      busy_sample_percent: 0, elapsed_seconds: 22,
      minute_averages: [{ minute: 0, average: 6.5 }],
    } },
  } as Status;
  render(<CafeShift status={status} onCamera={() => {}} />);
  expect(screen.getByText(/Average people outside the staff-only side: 3.2/)).toBeInTheDocument();
  expect(screen.getByText(/Peak in that area: 5/)).toBeInTheDocument();
  expect(screen.getByText(/not verified customers/)).toBeInTheDocument();
});
