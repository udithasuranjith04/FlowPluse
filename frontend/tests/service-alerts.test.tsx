import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { deriveServiceSignals, ServiceAlertsPage } from "../src/ServiceAlerts";
import type { Observation, Status } from "../src/types";

const healthy = {
  camera_id: "local-camera-1", state: "LIVE", mode: "LIVE", ai_state: "active", detection_target: "person",
  continuous_frames_verified: true, processed_frame_age_seconds: 0.2,
} as Status;

it("does not create a fake queue alert from a starter zone", () => {
  const queue = {
    id: "q", type: "possible_queue_buildup", state: "active", camera_id: "local-camera-1",
    review_status: "unreviewed", zone_id: "quick-waiting-area",
    zone_name: "Starter waiting area · adjust location", started_at: new Date().toISOString(),
  } as Observation;
  expect(deriveServiceSignals(healthy, [queue])).toEqual([]);
  expect(deriveServiceSignals(healthy, [{ ...queue, id: "real", zone_id: "counter", zone_name: "Counter waiting area" }])[0]?.title).toBe("Possible waiting-area pressure");
});

it("requires sustained activity, instead of one sudden count spike", () => {
  const history = [...Array(62).fill(2), ...Array(17).fill(2), 12].map((people, i) => ({ at: new Date(1_700_000_000_000 + 500 * i).toISOString(), people }));
  expect(deriveServiceSignals({ ...healthy, people_count_history: history })).toEqual([]);
  const sustained = [...Array(62).fill(2), ...Array(18).fill(7)].map((people, i) => ({ at: new Date(1_700_000_000_000 + 500 * i).toISOString(), people }));
  expect(deriveServiceSignals({ ...healthy, people_count_history: sustained })[0]?.title).toBe("Visible activity is rising");
});

it("suppresses service claims when camera health is uncertain", () => {
  const status = { ...healthy, processed_frame_age_seconds: 6, people_count_history: Array(35).fill({ at: "2026-11-02T10:00:00Z", people: 20 }) };
  const signals = deriveServiceSignals(status);
  expect(signals).toHaveLength(1);
  expect(signals[0].title).toBe("Check your camera");
});

it("shows the owner an automatic alert page rather than a manual review queue", () => {
  render(<ServiceAlertsPage status={healthy} events={[]} onCamera={() => {}} />);
  expect(screen.getByRole("heading", { name: "Know when to check in." })).toBeInTheDocument();
  expect(screen.getByText("No immediate service signal")).toBeInTheDocument();
  expect(screen.queryByText(/mark false alarm/i)).not.toBeInTheDocument();
});


it("uses a confirmed guest-facing area to measure rising activity when configured", () => {
  const full = [...Array(62).fill(10), ...Array(18).fill(10)].map((people, i) => ({
    at: new Date(1_700_000_000_000 + i * 500).toISOString(), people,
  }));
  const guest = [...Array(62).fill(1), ...Array(18).fill(5)];
  const signals = deriveServiceSignals({
    ...healthy, staff_only_region: "left", people_count_history: full,
    automatic_insights: { guest_area_recent: guest, session_summary: { elapsed_seconds: 40 } } as unknown as Status["automatic_insights"],
  });
  expect(signals[0]?.title).toBe("Visible activity is rising");
  expect(signals[0]?.detail).toContain("guest-facing area");
});


it("reports a disconnected active camera as attention, not a reassuring all-clear", () => {
  const signals = deriveServiceSignals({ ...healthy, state: "STALE", ai_state: "paused" });
  expect(signals[0].level).toBe("attention");
  expect(signals[0].title).toBe("Check your camera");
  expect(deriveServiceSignals({ ...healthy, state: "OFFLINE", ai_state: "paused" })[0].level).toBe("info");
});


it("suppresses operational pressure suggestions after the camera viewpoint changes", () => {
  const signals = deriveServiceSignals({ ...healthy, view_shift_detected: true,
    people_count_history: Array(40).fill({ at: new Date().toISOString(), people: 9 }),
  });
  expect(signals).toHaveLength(1);
  expect(signals[0].title).toBe("Camera view changed");
  expect(signals[0].level).toBe("info");
});
