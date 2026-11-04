
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import App from "../src/App";
import type { Observation, Status } from "../src/types";

class SocketStub {
  close() {}
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

function mockApi(status: Partial<Status> | null = null, event?: Observation) {
  vi.stubGlobal("WebSocket", SocketStub);

  return vi.spyOn(globalThis, "fetch").mockImplementation(async (url, init) => {
    const path = String(url);

    if (init?.method === "PATCH" && event) {
      event.review_status = JSON.parse(String(init.body)).review_status;
      return { ok: true, json: async () => ({ ...event }) } as Response;
    }

    const response: unknown = path.includes("/api/system/status")
      ? status
      : path === "/api/cameras"
        ? []
        : path.includes("/api/events")
          ? { items: event ? [event] : [], total: event ? 1 : 0 }
          : path.includes("/api/local-camera/devices")
            ? { devices: [] }
            : [];

    return { ok: true, json: async () => response } as Response;
  });
}

it("shows camera-first onboarding and never draws old demo video as person analytics", async () => {
  mockApi({
    camera_id: "demo",
    mode: "REPLAY",
    state: "REPLAY",
    ai_state: "active",
    detection_target: "person",
  });

  render(<App />);

  expect(
  await screen.findByRole("heading", {
    name: "Know your floor at a glance.",
  }),
).toBeInTheDocument();

  expect(
    screen.queryByRole("img", { name: /Live person-detection camera/ }),
  ).not.toBeInTheDocument();

  expect(screen.getByText(/Legacy demonstration/)).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "About FlowPulse" }));

  expect(
    screen.getByRole("heading", { name: "Better service. Less guesswork." }),
  ).toBeInTheDocument();
});

it("separates archived traffic fixtures from genuine people observations and retains review actions", async () => {
  Object.defineProperty(HTMLDialogElement.prototype, "showModal", {
    configurable: true,
    value() {
      this.setAttribute("open", "");
    },
  });

  Object.defineProperty(HTMLDialogElement.prototype, "close", {
    configurable: true,
    value() {
      this.removeAttribute("open");
    },
  });

  const event: Observation = {
    id: "dwell-1",
    camera_id: "local-camera-1",
    type: "extended_dwell",
    severity: "review",
    zone_name: "Waiting area",
    zone_id: "waiting",
    track_id: "local:1",
    state: "active",
    review_status: "unreviewed",
    started_at: "2026-11-02T10:00:00Z",
    ended_at: null,
    explanation: "Tracked footpoint remained in zone",
    features: { observed_seconds: 15 },
    quality_flags: [],
    rule_parameters: {} as Observation["rule_parameters"],
    model_version: "YOLO11n",
    source_mode: "LIVE",
    evidence_url: null,
  };

  const fetcher = mockApi(
    {
      camera_id: "local-camera-1",
      mode: "LIVE",
      state: "LIVE",
      ai_state: "active",
      detection_target: "person",
    },
    event,
  );

  render(<App />);

  fireEvent.click(
  await screen.findByRole("button", { name: "System health" })
);

fireEvent.click(
  screen.getByText("Historical observation archive").closest("summary")!
);

  fireEvent.click(
    await screen.findByRole("button", { name: /Extended dwell/ }),
  );

  expect(screen.getByRole("dialog")).toHaveTextContent("Waiting area");

  fireEvent.click(screen.getByRole("button", { name: "Mark false alarm" }));

  await waitFor(() => expect(event.review_status).toBe("false_alarm"));

  expect(
    fetcher.mock.calls.some(
      ([path, init]) =>
        String(path).endsWith("/dwell-1/review") && init?.method === "PATCH",
    ),
  ).toBe(true);
});

it("shows backend connection failure rather than fabricated camera metrics", async () => {
  vi.stubGlobal("WebSocket", SocketStub);

  vi.spyOn(globalThis, "fetch").mockRejectedValue(
    new Error("Backend unavailable"),
  );

  render(<App />);

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Backend unavailable",
  );

  expect(screen.getAllByText("—").length).toBeGreaterThan(0);
});
