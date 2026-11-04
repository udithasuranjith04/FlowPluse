import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { FlowDashboard } from "../src/FlowDashboard";
import ZoneEditor from "../src/ZoneEditor";
import type { Camera, Status } from "../src/types";

it("shows actual people flow counters without calling them room census", () => {
  const status: Status = {
    camera_id: "local-camera-1",
    mode: "LIVE",
    state: "LIVE",
    model: "yolo11n.pt",
    device: "cpu",
    ai_state: "active",
    frame_timestamp: "2026-11-02T10:00:00Z",
    frame_age_seconds: 0.2,
    processing_delay_ms: 50,
    processed_frame_age_seconds: 0.2,
    ingest_fps: 8,
    processed_fps: 2,
    latency_p50_ms: 40,
    latency_p95_ms: 65,
    dropped_frames: 0,
    reconnect_count: 0,
    queue_depth: 0,
    active_tracks: 2,
    session_events: 0,
    uptime_seconds: 60,
    last_error: null,
    quality_flags: [],
    rule_debug: [],
    evidence_enabled: false,
    evidence_error: null,
    logs: [],
    detection_target: "person",
    visible_people: 2,
    temporal_rules_enabled: true,
    flow: {
      entries: 3,
      exits: 1,
      zone_counts: { waiting: 2 },
      lines: [
        { id: "door", name: "Door", points: [[0.2, 0.5], [0.8, 0.5]] },
      ],
    },
  };
  const toZones = vi.fn();
  render(<FlowDashboard status={status} onZones={toZones} />);
  expect(screen.getByText("People visible")).toBeInTheDocument();
  expect(screen.getByText("3")).toBeInTheDocument();
  expect(screen.getByText("1")).toBeInTheDocument();
  expect(screen.getByText("2 in zone")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /Configure zones and lines/ }));
  expect(toZones).toHaveBeenCalledOnce();
});

it("drafts two-point oriented line and saves it through the existing zones API", async () => {
  const payload = { zones: [], lines: [], rules: { min_confidence: 0.35 } };
  const fetcher = vi.spyOn(globalThis, "fetch").mockResolvedValue({
    ok: true, json: async () => payload,
  } as Response);
  render(<ZoneEditor people camera={{ id: "local-camera-1", name: "iPhone" } as Camera} onSave={() => {}} />);
  await screen.findByRole("button", { name: "Draw two-point counting line" });
  fireEvent.click(screen.getByRole("button", { name: "Draw two-point counting line" }));
  for (const [x, y] of [[0.2, 0.5], [0.8, 0.5]]) {
    fireEvent.change(screen.getByLabelText("X"), { target: { value: x } });
    fireEvent.change(screen.getByLabelText("Y"), { target: { value: y } });
    fireEvent.click(screen.getByRole("button", { name: "Add point" }));
  }
  fireEvent.click(screen.getByRole("button", { name: "Add counting line" }));
  fireEvent.click(screen.getByRole("button", { name: "Save configuration" }));
  await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2));
  const saved = JSON.parse(String(fetcher.mock.calls[1][1]?.body));
  expect(saved.lines).toHaveLength(1);
  expect(saved.lines[0].points).toEqual([[0.2, 0.5], [0.8, 0.5]]);
  fetcher.mockRestore();
});
