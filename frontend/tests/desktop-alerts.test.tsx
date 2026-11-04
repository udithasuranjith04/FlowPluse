import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { useDesktopAlerts } from "../src/ServiceAlerts";
import type { Status } from "../src/types";

const rising = {
  camera_id: "local-camera-1", state: "LIVE", ai_state: "active", mode: "LIVE",
  detection_target: "person", continuous_frames_verified: true,
  processed_frame_age_seconds: 0.3,
  // Sustained increase: 80 frames at 2 FPS cover 39.5 seconds, clearing
  // the 72-sample / 30-second evidence gate for an attention notification.
  people_count_history: [...Array(62).fill(2), ...Array(18).fill(7)].map((people, i) => ({
    at: new Date(1_700_000_000_000 + 500 * i).toISOString(), people,
  })),
} as Status;

afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

function Harness({ status, page }: { status: Status; page: string }) {
  const desktop = useDesktopAlerts(status, []);
  return <section><span>{page}</span><button onClick={() => void desktop.toggle()}>{desktop.enabled ? "Disable" : "Enable"}</button></section>;
}

it("keeps desktop alerts active across page changes and sends each active signal once", async () => {
  const received: string[] = [];
  class MockNotification {
    static permission: NotificationPermission = "granted";
    static requestPermission = vi.fn(async () => "granted" as NotificationPermission);
    constructor(title: string) { received.push(title); }
  }
  vi.stubGlobal("Notification", MockNotification);
  const ui = render(<Harness status={rising} page="Live café" />);
  expect(received).toHaveLength(0);
  fireEvent.click(screen.getByRole("button", { name: "Enable" }));
  await waitFor(() => expect(received).toHaveLength(1));
  ui.rerender(<Harness status={{ ...rising }} page="Shift summary" />);
  expect(screen.getByText("Shift summary")).toBeInTheDocument();
  expect(received).toHaveLength(1);
  fireEvent.click(screen.getByRole("button", { name: "Disable" }));
  expect(received).toHaveLength(1);
});
