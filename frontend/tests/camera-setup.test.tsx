import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { CameraSetup } from "../src/CameraSetup";
import type { Status } from "../src/types";

afterEach(() => vi.restoreAllMocks());
const cameras = [
  { index: 0, name: "Mac built-in camera", device_id: "mac" },
  { index: 1, name: "iPhone Camera", device_id: "iphone-stable-id" },
];
function respond(devices = cameras) {
  vi.spyOn(globalThis, "fetch").mockResolvedValue({ ok: true, json: async () => ({ devices, message: "Discovery available" }) } as Response);
}
it("selects a detected iPhone by name but never previews without explicit consent", async () => {
  respond();
  const activate = vi.fn(async () => true);
  render(<CameraSetup status={null} busy={false} activateLocal={activate} />);
  expect(screen.getByRole("button", { name: "Preview camera" })).toBeDisabled();
  const select = await screen.findByLabelText("Available camera device") as HTMLSelectElement;
  expect(select.value).toBe("1");
  fireEvent.click(screen.getByRole("checkbox", { name: /I control this camera/ }));
  fireEvent.click(screen.getByRole("button", { name: "Preview camera" }));
  await waitFor(() => expect(activate).toHaveBeenCalledWith(1, true, "iphone-stable-id"));
  expect(screen.getByRole("button", { name: "Start monitoring" })).toBeDisabled();
});
it("requires a verified preview and fresh consent after changing the selected camera", async () => {
  respond();
  const activate = vi.fn(async () => true);
  const status = {
    camera_id: "local-camera-1", preview_only: true, ai_state: "active", frame_id: "frame-01", continuous_frames_verified: true,
  } as Status;
  render(<CameraSetup status={status} busy={false} activateLocal={activate} />);
  await screen.findByRole("option", { name: /iPhone Camera/ });
  expect(screen.getByRole("button", { name: "Start monitoring" })).toBeDisabled();
  fireEvent.click(screen.getByRole("checkbox", { name: /I control this camera/ }));
  fireEvent.click(screen.getByRole("button", { name: "Start monitoring" }));
  await waitFor(() => expect(activate).toHaveBeenCalledWith(1, false, "iphone-stable-id"));
  fireEvent.change(screen.getByLabelText("Available camera device"), { target: { value: "0" } });
  expect(screen.getByRole("checkbox", { name: /I control this camera/ })).not.toBeChecked();
  expect(screen.getByRole("button", { name: "Start monitoring" })).toBeDisabled();
});
it("handles camera-discovery failure and never assumes a live camera", async () => {
  vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("Permission denied"));
  render(<CameraSetup status={null} busy={false} activateLocal={vi.fn(async () => false)} />);
  expect(await screen.findByRole("status")).toHaveTextContent("Permission denied");
  expect(screen.getByRole("button", { name: "Preview camera" })).toBeDisabled();
});
