import { useEffect, useRef, useState } from "react";
import { api } from "./api";
import type { Camera, EventPage, Metric, Status } from "./types";

export function useLive() {
  const [status, setStatus] = useState<Status | null>(null);
  const [initialLoading, setInitialLoading] = useState(true);
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [events, setEvents] = useState<EventPage>({
    items: [],
    total: 0,
    limit: 50,
    offset: 0,
  });
  const [metrics, setMetrics] = useState<Metric[]>([]);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState("");
  const sourceEpoch = useRef(0);
  const controlRevision = useRef(0);
  const pendingSource = useRef<string | null>(null);
  const refreshRef = useRef<() => void>(() => {});
  useEffect(() => {
    let disposed = false,
      socket: WebSocket | undefined,
      retry: ReturnType<typeof setTimeout>;
    let attempts = 0,
      refreshing = false,
      refreshAgain = false,
      currentCamera = "",
      liveStatusReceived = false,
      statusRevision = 0;
    function acceptsRevision(next: Status) {
      const revision = next.control_revision || 0;
      if (revision < controlRevision.current) return false;
      controlRevision.current = revision;
      return true;
    }
    async function refresh() {
      if (refreshing) {
        refreshAgain = true;
        return;
      }
      refreshing = true;
      const epoch = sourceEpoch.current;
      const revision = statusRevision;
      try {
        const s = await api<Status>("/api/system/status");
        const [c, e, m] = await Promise.all([
          api<Camera[]>("/api/cameras"),
          api<EventPage>(
            `/api/events?limit=50&camera_id=${encodeURIComponent(s.camera_id)}`,
          ),
          api<Metric[]>("/api/metrics/series?window=300"),
        ]);
        if (
          !disposed &&
          epoch === sourceEpoch.current &&
          (!pendingSource.current || s.camera_id === pendingSource.current)
          && acceptsRevision(s)
        ) {
          // An open socket does not guarantee further status messages. Use
          // polling unless a newer socket status arrived during this fetch;
          // never accept an old-source response over a selected source.
          if (
            revision === statusRevision &&
            (!liveStatusReceived ||
              s.camera_id === currentCamera ||
              pendingSource.current === s.camera_id)
          )
            setStatus(s);
          setCameras(c);
          setEvents(e);
          setMetrics(m);
          setError("");
        }
      } catch (e) {
        if (!disposed && epoch === sourceEpoch.current) {
          setError(e instanceof Error ? e.message : "Backend unavailable");
          setStatus((old) =>
            old
              ? {
                  ...old,
                  state: "UNREACHABLE",
                  ai_state: "paused",
                  last_error: "Connection to the backend is unavailable.",
                }
              : null,
          );
        }
      } finally {
        if (!disposed) setInitialLoading(false);
        refreshing = false;
        if (refreshAgain && !disposed) {
          refreshAgain = false;
          void refresh();
        }
      }
    }
    function connect() {
      if (disposed) return;
      const connection = new WebSocket(
        `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/live`,
      );
      socket = connection;
      const current = () => !disposed && socket === connection;
      connection.onopen = () => {
        if (!current()) return;
        attempts = 0;
        setConnected(true);
        void refresh();
      };
      connection.onmessage = (event) => {
        if (!current()) return;
        try {
          const message = JSON.parse(event.data);
          if (message.version !== 1) return;
          if (message.type === "status") {
            if (
              pendingSource.current &&
              message.data.camera_id !== pendingSource.current
            )
              return;
            if (!acceptsRevision(message.data)) return;
            pendingSource.current = null;
            liveStatusReceived = true;
            statusRevision += 1;
            setStatus(message.data);
            setInitialLoading(false);
            if (currentCamera !== message.data.camera_id) {
              currentCamera = message.data.camera_id;
              sourceEpoch.current += 1;
              setEvents({ items: [], total: 0, limit: 50, offset: 0 });
              setMetrics([]);
              void refresh();
            }
          }
          if (message.type === "metrics")
            setMetrics((old) =>
              old.at(-1)?.timestamp === message.data.timestamp
                ? old
                : [...old.slice(-599), message.data],
            );
          if (message.type.startsWith("event_")) {
            if (
              message.data.camera_id !==
              (pendingSource.current || currentCamera)
            )
              return;
            setEvents((old) => ({
              ...old,
              items: [
                message.data,
                ...old.items.filter((e) => e.id !== message.data.id),
              ]
                .sort((a, b) => b.started_at.localeCompare(a.started_at))
                .slice(0, 50),
            }));
          }
        } catch {
          setError("Unable to read a live update. Retrying with server data.");
        }
      };
      connection.onclose = () => {
        if (!current()) return;
        socket = undefined;
        setConnected(false);
        liveStatusReceived = false;
        setStatus((old) =>
          old ? { ...old, state: ["PAUSED", "OFFLINE"].includes(old.state) ? old.state : "STALE", ai_state: "paused" } : null,
        );
        retry = setTimeout(connect, Math.min(30000, 1000 * 2 ** attempts++));
      };
      connection.onerror = () => {
        if (current()) connection.close();
      };
    }
    refreshRef.current = () => void refresh();
    // Do not trap users on a branded loading screen if the backend hangs.
    const startupTimeout = setTimeout(() => { if (!disposed) setInitialLoading(false); }, 7000);
    void refresh();
    // Defer acquisition so Strict Mode can clean up its probe before opening a socket.
    retry = setTimeout(connect, 0);
    const polling = setInterval(() => void refresh(), 5000);
    return () => {
      disposed = true;
      clearTimeout(retry);
      clearTimeout(startupTimeout);
      clearInterval(polling);
      refreshRef.current = () => {};
      if (socket) {
        socket.onopen =
          socket.onmessage =
          socket.onclose =
          socket.onerror =
            null;
        socket.close();
      }
    };
  }, []);
  return {
    status,
    initialLoading,
    cameras,
    events,
    metrics,
    connected,
    error,
    refresh: () => refreshRef.current(),
    sourceChanged: (next: Status) => {
      // The activation response is the first authoritative status for this
      // request. Keep the pending guard until that source arrives over WS.
      if (pendingSource.current === next.camera_id) {
        controlRevision.current = Math.max(controlRevision.current, next.control_revision || 0);
        setStatus(next);
      }
    },
    controlChanged: (next: Status) => {
      controlRevision.current = Math.max(controlRevision.current, next.control_revision || 0);
      sourceEpoch.current += 1;
      pendingSource.current = next.camera_id;
      setStatus(next);
    },
    beginSourceChange: (id: string) => {
      sourceEpoch.current += 1;
      pendingSource.current = id;
      setEvents({ items: [], total: 0, limit: 50, offset: 0 });
      setMetrics([]);
      setStatus((old) =>
        old
          ? {
              ...old,
              camera_id: id,
              mode:
                cameras.find((c) => c.id === id)?.mode ||
                (id.startsWith("digitraffic-") ? "SNAPSHOT" : id.startsWith("local-camera-") ? "LIVE" : "REPLAY"),
              state: "CONNECTING",
              continuous_frames_verified: false,
              consecutive_frames_received: 0,
              device_released: undefined,
              preview_only: false,
              monitoring_zones_configured: undefined,
              ai_state: "loading",
              frame_timestamp: null,
              frame_id: null,
              source_timestamp: null,
              source_age_seconds: null,
              source_image_sha256: null,
              visible_vehicles: undefined,
              visible_people: undefined,
              detection_target: undefined,
              detections: [],
              active_tracks: 0,
              session_events: 0,
              last_error: null,
              model: "Waiting for selected source",
              inference_ms: null,
              latency_p50_ms: null,
              latency_p95_ms: null,
              processing_delay_ms: null,
              quality_flags: [],
            }
          : null,
      );
    },
    sourceChangeFailed: (message: string) => {
      setStatus((old) =>
        old
          ? {
              ...old,
              state: "ERROR",
              ai_state: "paused",
              last_error: message,
            }
          : null,
      );
      refreshRef.current();
    },
  };
}
