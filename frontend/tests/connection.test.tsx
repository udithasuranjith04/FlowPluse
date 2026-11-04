import { act, renderHook } from "@testing-library/react";
import { createElement, StrictMode, type ReactNode } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { useLive } from "../src/useLive";
import type { Status } from "../src/types";

class Socket {
  static instances: Socket[] = [];
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  close = vi.fn();
  constructor() {
    Socket.instances.push(this);
  }
  status(state: string) {
    this.onmessage?.({
      data: JSON.stringify({
        version: 1,
        type: "status",
        data: {
          camera_id: "demo",
          mode: "REPLAY",
          state,
          ai_state: "active",
        },
      }),
    });
  }
}

beforeEach(() => {
  vi.useFakeTimers();
  Socket.instances = [];
  vi.stubGlobal("WebSocket", Socket);
  vi.spyOn(globalThis, "fetch").mockImplementation(
    async (path) =>
      ({
        ok: true,
        json: async () =>
          String(path).includes("system/status")
            ? {
                camera_id: "demo",
                mode: "REPLAY",
                state: "REPLAY",
                ai_state: "active",
              }
            : String(path).includes("events")
              ? { items: [], total: 0 }
              : [],
      }) as Response,
  );
});
afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});
const tick = (ms = 0) =>
  act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });

it.each([false, true])("finishes source selection through polling when the open socket stops updating (selected status received: %s)", async (sourceStatusReceived) => {
  const { result, unmount } = renderHook(useLive);
  await tick();
  const socket = Socket.instances[0];
  act(() => {
    socket.onopen?.();
    socket.status("REPLAY");
  });
  await tick();
  const id = "digitraffic-C1000101";
  act(() => {
    result.current.beginSourceChange(id);
    result.current.sourceChanged({
      camera_id: id,
      mode: "SNAPSHOT",
      state: "CONNECTING",
      ai_state: "loading",
      model: "Loading selected model",
    } as Status);
  });
  expect(result.current.status?.model).toBe("Loading selected model");
  if (sourceStatusReceived) act(() => socket.onmessage?.({
    data: JSON.stringify({ version: 1, type: "status", data: {
      camera_id: id, state: "CONNECTING", mode: "SNAPSHOT", ai_state: "loading",
    } }),
  }));
  vi.mocked(fetch).mockImplementation(async (path) => ({
    ok: true,
    json: async () => String(path).includes("system/status")
      ? { camera_id: id, mode: "SNAPSHOT", state: "SNAPSHOT", ai_state: "active", frame_id: "processed-real-image", visible_vehicles: 0 }
      : String(path).includes("events") ? { items: [], total: 0 } : [],
  }) as Response);
  if (!sourceStatusReceived) act(() => socket.status("REPLAY"));
  await tick(5000);
  expect(result.current.status?.frame_id).toBe("processed-real-image");
  expect(result.current.status?.visible_vehicles).toBe(0);
  expect(result.current.status?.camera_id).toBe(id);
  unmount();
});

it("keeps one socket through Strict Mode and refresh, then releases it", async () => {
  const { result, unmount } = renderHook(useLive, {
    wrapper: ({ children }: { children: ReactNode }) =>
      createElement(StrictMode, null, children),
  });
  await tick();
  expect(Socket.instances).toHaveLength(1);
  const socket = Socket.instances[0];
  act(() => socket.onopen?.());
  await tick();
  act(() => result.current.refresh());
  await tick();
  expect(Socket.instances).toHaveLength(1);
  expect(socket.close).not.toHaveBeenCalled();
  unmount();
  expect(socket.close).toHaveBeenCalledOnce();
  expect(socket.onmessage).toBeNull();
  await tick(30000);
  expect(Socket.instances).toHaveLength(1);
});

it("receives status and reconnects after a drop, ignoring retired callbacks", async () => {
  const { result, unmount } = renderHook(useLive);
  await tick();
  const first = Socket.instances[0];
  act(() => {
    first.onopen?.();
    first.status("REPLAY");
  });
  await tick();
  expect(result.current.connected).toBe(true);
  const lateMessage = first.onmessage;
  const close = first.onclose;
  act(() => {
    close?.();
    close?.();
  });
  expect(result.current.connected).toBe(false);
  expect(result.current.status?.state).toBe("STALE");
  expect(result.current.status?.ai_state).toBe("paused");
  await tick(999);
  expect(Socket.instances).toHaveLength(1);
  await tick(1);
  expect(Socket.instances).toHaveLength(2);
  act(() => {
    Socket.instances[1].onopen?.();
    Socket.instances[1].status("REPLAY");
  });
  await tick();
  act(() =>
    lateMessage?.({
      data: JSON.stringify({
        version: 1,
        type: "status",
        data: { state: "OFFLINE" },
      }),
    }),
  );
  expect(result.current.connected).toBe(true);
  expect(result.current.status?.state).toBe("REPLAY");
  act(() => Socket.instances[1].onclose?.());
  unmount();
  await tick(30000);
  expect(Socket.instances).toHaveLength(2);
});

it("clears the demo on real-source selection and ignores late demo status", async () => {
  const { result, unmount } = renderHook(useLive);
  await tick();
  const socket = Socket.instances[0];
  act(() => {
    socket.onopen?.();
    socket.status("REPLAY");
  });
  await tick();
  act(() => result.current.beginSourceChange("digitraffic-C1000101"));
  expect(result.current.status?.camera_id).toBe("digitraffic-C1000101");
  expect(result.current.status?.state).toBe("CONNECTING");
  expect(result.current.status?.frame_id).toBeNull();
  act(() => socket.status("REPLAY"));
  expect(result.current.status?.camera_id).toBe("digitraffic-C1000101");
  act(() =>
    socket.onmessage?.({
      data: JSON.stringify({
        version: 1,
        type: "status",
        data: {
          camera_id: "digitraffic-C1000101",
          mode: "SNAPSHOT",
          state: "SNAPSHOT",
          ai_state: "active",
          frame_id: "real-frame",
        },
      }),
    }),
  );
  await tick();
  act(() => result.current.refresh());
  await tick();
  expect(result.current.status?.frame_id).toBe("real-frame");
  expect(result.current.status?.camera_id).toBe("digitraffic-C1000101");
  unmount();
});

it("never resurrects camera status after a stop acknowledgement or relabels pause as stale", async () => {
  const { result, unmount } = renderHook(useLive);
  await tick();
  const socket = Socket.instances[0];
  act(() => socket.onopen?.());
  const message = (state: string, revision: number) => socket.onmessage?.({ data: JSON.stringify({
    version: 1, type: "status", data: { camera_id: "demo", state, mode: "REPLAY", ai_state: "active", control_revision: revision },
  }) });
  act(() => message("REPLAY", 10));
  act(() => result.current.controlChanged({ camera_id: "demo", mode: "REPLAY", state: "PAUSED", ai_state: "paused", control_revision: 20 } as Status));
  act(() => message("REPLAY", 10));
  expect(result.current.status?.state).toBe("PAUSED");
  act(() => socket.onclose?.());
  expect(result.current.status?.state).toBe("PAUSED");
  act(() => result.current.controlChanged({ camera_id: "demo", mode: "REPLAY", state: "OFFLINE", ai_state: "paused", control_revision: 30 } as Status));
  await tick(5000); // Old REST fixture is also rejected by control revision.
  expect(result.current.status?.state).toBe("OFFLINE");
  expect(result.current.status?.control_revision).toBe(30);
  unmount();
});
