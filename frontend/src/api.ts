export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(
      body.error?.message || `Request failed (${response.status})`,
    );
  }
  return response.json() as Promise<T>;
}
export const time = (value?: string | null) =>
  value
    ? new Date(value).toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      })
    : "Awaiting frame";
export const duration = (seconds: number) =>
  seconds >= 3600
    ? `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`
    : `${Math.floor(seconds / 60)}m ${Math.floor(seconds % 60)}s`;
export const title = (type: string) =>
  type === "potential_stopped_vehicle"
    ? "Potential stopped vehicle"
    : type === "congestion_buildup"
      ? "Congestion buildup"
      : type === "extended_dwell"
        ? "Extended dwell"
        : type === "possible_queue_buildup"
          ? "Possible queue buildup"
          : type.replaceAll("_", " ");
