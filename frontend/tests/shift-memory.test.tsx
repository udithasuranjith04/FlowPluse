import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { ShiftMemory } from "../src/ShiftMemory";
import type { Status } from "../src/types";

afterEach(() => vi.restoreAllMocks());

it("keeps cross-shift storage off until the owner explicitly opts in", async () => {
  const fetcher = vi.spyOn(globalThis, "fetch").mockImplementation(async (_url, init) => {
    const enabled = init?.method === "PUT";
    return { ok: true, json: async () => ({ enabled, saved_shifts: [], retention_days: 30, minimum_samples: 300, minimum_duration_seconds: 240 }) } as Response;
  });
  render(<ShiftMemory status={null}/>);
  expect(await screen.findByText("No shift history is retained")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Enable local aggregate memory" }));
  await waitFor(() => expect(screen.getByText("0 previous shifts saved")).toBeInTheDocument());
  expect(fetcher.mock.calls.some(([, init]) => init?.method === "PUT")).toBe(true);
  expect(screen.getByText(/Sessions need 300 healthy frames and 4 minutes/)).toBeInTheDocument();
});


it("uses the median of eligible saved sessions and only compares a stable current shift", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue({
    ok: true,
    json: async () => ({
      enabled: true, retention_days: 30, minimum_samples: 300, minimum_duration_seconds: 240,
      saved_shifts: [2, 4, 20].map((average_visible) => ({
        created_at: "2026-11-01T10:00:00Z", elapsed_seconds: 300,
        processed_samples: 400, average_visible, peak_visible: average_visible + 1,
      })),
    }),
  } as Response);
  const live = {
    camera_id: "local-camera-1", view_shift_detected: false,
    automatic_insights: { session_summary: { elapsed_seconds: 300, average_visible: 5 } },
  } as unknown as Status;
  const view = render(<ShiftMemory status={live}/>);
  expect(await screen.findByText(/5.0 average now.*\+1.0 vs reference/)).toBeInTheDocument();
  expect(screen.getByText(/Median of 3 previous compatible records: 4.0/)).toBeInTheDocument();
  view.rerender(<ShiftMemory status={{ ...live, view_shift_detected: true }}/>);
  expect(screen.getByText(/Collect 4 minutes of stable monitoring/)).toBeInTheDocument();
});
