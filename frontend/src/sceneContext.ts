/** Optional operator-assigned context for anonymous image-grid hotspots.
 * This is display metadata, not a model prediction, queue classifier or people profile.
 * It is browser-local and scoped to one fixed camera view. */
export type SceneArea = "unassigned" | "seating" | "counter" | "entrance" | "other";
export type SceneTags = Record<string, SceneArea>;

export const SCENE_AREAS: { value: SceneArea; label: string }[] = [
  { value: "unassigned", label: "Unlabeled camera area" },
  { value: "seating", label: "Seating area" },
  { value: "counter", label: "Counter / pickup area" },
  { value: "entrance", label: "Entrance / walkway" },
  { value: "other", label: "Other confirmed area" },
];

const cameraPattern = /^local-camera-[A-Za-z0-9_-]{1,80}$/;
const hotspotPattern = /^scene-[0-3]-[0-5]$/;
const keyFor = (cameraId: string) => `flowpulse.scene-tags.v1.${cameraId}`;

export function readSceneTags(cameraId: string | undefined): SceneTags {
  if (!cameraId || !cameraPattern.test(cameraId)) return {};
  try {
    const raw: unknown = JSON.parse(localStorage.getItem(keyFor(cameraId)) || "{}");
    if (!raw || typeof raw !== "object" || Array.isArray(raw)) return {};
    return Object.fromEntries(
      Object.entries(raw).filter(([id, label]) =>
        hotspotPattern.test(id) && SCENE_AREAS.some((item) => item.value === label) && label !== "unassigned",
      ),
    ) as SceneTags;
  } catch {
    // Browser storage can be disabled; the monitoring UI must still work.
    return {};
  }
}

export function writeSceneTag(cameraId: string | undefined, hotspotId: string, label: SceneArea): SceneTags {
  if (!cameraId || !cameraPattern.test(cameraId) || !hotspotPattern.test(hotspotId)) return {};
  const next = readSceneTags(cameraId);
  if (label === "unassigned") delete next[hotspotId];
  else if (SCENE_AREAS.some((area) => area.value === label)) next[hotspotId] = label;
  try {
    if (Object.keys(next).length === 0) localStorage.removeItem(keyFor(cameraId));
    else localStorage.setItem(keyFor(cameraId), JSON.stringify(next));
  } catch { /* Use the in-memory result for the current render even if storage is disabled. */ }
  return next;
}

export function clearSceneTags(cameraId: string | undefined): void {
  if (!cameraId || !cameraPattern.test(cameraId)) return;
  try { localStorage.removeItem(keyFor(cameraId)); } catch { /* Storage may be disabled. */ }
}

export function sceneAreaGuidance(area: SceneArea, pattern: "longer_stays" | "movement" | "frequent_presence"): string {
  if (area === "seating") return "Owner-labeled seating: low movement is expected. This is not a service delay or table-turnover estimate.";
  if (area === "counter") return "Owner-labeled counter: repeated presence could be useful to inspect, but does not establish a queue or wait time.";
  if (area === "entrance") return "Owner-labeled entrance/walkway: movement here is not a verified arrival or departure count.";
  if (area === "other") return "Owner-labeled location: compare this pattern with how the space is actually used before acting.";
  return pattern === "longer_stays"
    ? "Unlabeled area: remaining still may simply mean seating. Label the area to interpret it in context."
    : "Unlabeled area: the camera has not determined whether this is seating, a counter or a walkway.";
}
