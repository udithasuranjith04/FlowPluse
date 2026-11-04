/**
 * Browser-only presentation memory for sparse anonymous person detections.
 *
 * A confirmed outline is NEVER a predicted location and it NEVER contributes to
 * people counts, service alerts, shift history or backend evidence. We keep its
 * last sampled geometry steady between inference frames. Missing/delayed evidence
 * becomes an explicitly unverified amber hint and expires after a hard limit.
 */

export interface SampledOverlay {
  id: string;
  box: number[];
  confidence: number;
  held?: boolean;
  held_age_seconds?: number;
}

export interface OverlaySample {
  source: string;
  sample: string;
  capturedAtMs: number;
  tracks: SampledOverlay[];
}

export interface RememberedOverlay {
  visualId: string;
  sourceId: string;
  box: [number, number, number, number];
  confirmedAtMs: number;
  missingAtMs: number | null;
}

export interface OverlayMemory {
  source: string;
  sample: string;
  lastSampleAtMs: number;
  tracks: RememberedOverlay[];
  nextId: number;
}

export interface DisplayOverlay extends RememberedOverlay {
  state: "confirmed" | "last-seen";
}

export const emptyOverlayMemory = (): OverlayMemory => ({
  source: "", sample: "", lastSampleAtMs: 0, tracks: [], nextId: 0,
});

const CONFIRMED_MAX_AGE_MS = 1750;
const MISSING_HINT_MAX_AGE_MS = 1550;
const DELAYED_HINT_MAX_AGE_MS = 2450;

function validBox(box: number[]): box is [number, number, number, number] {
  return box.length === 4 && box.every((n) => Number.isFinite(n) && n >= 0 && n <= 1) &&
    box[0] < box[2] && box[1] < box[3];
}

function iou(a: number[], b: number[]): number {
  const x = Math.max(0, Math.min(a[2], b[2]) - Math.max(a[0], b[0]));
  const y = Math.max(0, Math.min(a[3], b[3]) - Math.max(a[1], b[1]));
  const intersection = x * y;
  const aa = (a[2] - a[0]) * (a[3] - a[1]);
  const ab = (b[2] - b[0]) * (b[3] - b[1]);
  return intersection / (aa + ab - intersection || 1);
}

/** Reconcile only on genuinely new AI samples, never on repeated WebSocket polls. */
export function reconcileOverlaySample(
  memory: OverlayMemory, update: OverlaySample, nowMs: number,
): OverlayMemory {
  if (!update.source || !update.sample || !Number.isFinite(update.capturedAtMs) ||
      update.capturedAtMs > nowMs + 1000 || nowMs - update.capturedAtMs > 3000) {
    return emptyOverlayMemory();
  }
  const prior = memory.source === update.source ? memory : emptyOverlayMemory();
  // Polling the same inference must not extend a box's observed lifetime.
  if (prior.sample === update.sample) return prior;

  const available = prior.tracks.filter((track) =>
    update.capturedAtMs - track.confirmedAtMs <= DELAYED_HINT_MAX_AGE_MS &&
    update.capturedAtMs >= track.confirmedAtMs,
  );
  const matched = new Set<string>();
  const updated: RememberedOverlay[] = [];
  let nextId = prior.nextId;
  for (const raw of update.tracks.filter((track) => !track.held).slice(0, 32)) {
    if (!validBox(raw.box)) continue;
    // Exact anonymous tracker ID first. Geometry only bridges brief ID changes
    // for nearly identical boxes, and matching is strictly one-to-one.
    let match = available.find((old) => old.sourceId === raw.id && !matched.has(old.visualId));
    if (!match) {
      const options = available
        .filter((old) => !matched.has(old.visualId))
        .map((old) => ({ old, score: iou(old.box, raw.box) }))
        .filter((option) => option.score >= 0.62)
        .sort((a, b) => b.score - a.score);
      match = options[0]?.old;
    }
    const visualId = match?.visualId ?? `visual-${++nextId}`;
    matched.add(visualId);
    updated.push({
      visualId, sourceId: raw.id, box: [...raw.box],
      confirmedAtMs: update.capturedAtMs, missingAtMs: null,
    });
  }
  // Known person no longer detected in this sample: show amber for a short
  // grace period, without pretending the person was counted or is still there.
  for (const old of available) {
    if (!matched.has(old.visualId) && update.capturedAtMs - old.confirmedAtMs < MISSING_HINT_MAX_AGE_MS) {
      updated.push({ ...old, missingAtMs: old.missingAtMs ?? update.capturedAtMs });
      matched.add(old.visualId);
    }
  }
  // A newly opened tab may first receive backend-provided held outlines.
  // These are also amber only and have the same strict expiration.
  for (const raw of update.tracks.filter((track) => track.held)) {
    const heldAge = raw.held_age_seconds;
    if (!validBox(raw.box) || typeof heldAge !== "number" || !Number.isFinite(heldAge) ||
        heldAge < 0 || heldAge > 1.1 ||
        updated.some((track) => track.sourceId === raw.id)) continue;
    const confirmedAtMs = update.capturedAtMs - heldAge * 1000;
    if (nowMs - confirmedAtMs >= MISSING_HINT_MAX_AGE_MS) continue;
    updated.push({ visualId: `visual-${++nextId}`, sourceId: raw.id,
      box: [...raw.box], confirmedAtMs, missingAtMs: update.capturedAtMs });
  }
  return {
    source: update.source, sample: update.sample,
    lastSampleAtMs: update.capturedAtMs, tracks: updated.slice(0, 32), nextId,
  };
}

/** Solid stays visually steady between ordinary samples; stale becomes amber. */
export function presentOverlays(
  memory: OverlayMemory, nowMs: number, processedFps = 2, processingDelayMs = 0,
): DisplayOverlay[] {
  const cadence = Number.isFinite(processedFps) && processedFps > 0
    ? 1000 / processedFps : 500;
  const delay = Number.isFinite(processingDelayMs) && processingDelayMs > 0
    ? Math.min(550, processingDelayMs) : 0;
  const confirmedTtl = Math.min(CONFIRMED_MAX_AGE_MS, Math.max(1150, 2.4 * cadence + delay));
  return memory.tracks.flatMap((track) => {
    const age = nowMs - track.confirmedAtMs;
    if (!Number.isFinite(age) || age < -1000) return [];
    const explicitlyMissing = track.missingAtMs !== null;
    const deadline = explicitlyMissing ? MISSING_HINT_MAX_AGE_MS : DELAYED_HINT_MAX_AGE_MS;
    if (age >= deadline) return [];
    return [{ ...track, state: !explicitlyMissing && age <= confirmedTtl
      ? "confirmed" as const : "last-seen" as const }];
  });
}
