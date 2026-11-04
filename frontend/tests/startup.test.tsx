import { act, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import App from "../src/App";

class SilentSocket { close() {} }
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

it("shows the privacy-first brand while loading status and never starts a camera automatically", async () => {
  vi.stubGlobal("WebSocket", SilentSocket);
  let completeStatus!: (response: Response) => void;
  const statusPending = new Promise<Response>((resolve) => { completeStatus = resolve; });
  const requests: string[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (url) => {
    const path = String(url);
    requests.push(path);
    if (path.includes("/api/system/status")) return statusPending;
    const result = path.includes("/api/events") ? { items: [], total: 0 } : [];
    return { ok: true, json: async () => result } as Response;
  });
  render(<App />);
  expect(screen.getByRole("main", { name: "FlowPulse startup" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: /Understand spaces.*Respect people/s })).toBeInTheDocument();
  expect(screen.getByRole("status")).toHaveTextContent("Connecting to your local workspace");
  await act(async () => completeStatus({ ok: true, json: async () => ({
    camera_id: "none", mode: "LIVE", state: "OFFLINE", ai_state: "paused",
  }) } as Response));
  await waitFor(() => expect(screen.queryByRole("main", { name: "FlowPulse startup" })).not.toBeInTheDocument());
  expect(screen.getByRole("heading", { name: "Know your floor at a glance." })).toBeInTheDocument();
  expect(requests.every((path) => !path.includes("/activate") && !path.includes("/preview"))).toBe(true);
});

it("leaves the startup screen and shows a retryable error when the backend is offline", async () => {
  vi.stubGlobal("WebSocket", SilentSocket);
  vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("Backend unavailable"));
  render(<App />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Backend unavailable");
  expect(screen.queryByRole("main", { name: "FlowPulse startup" })).not.toBeInTheDocument();
});
