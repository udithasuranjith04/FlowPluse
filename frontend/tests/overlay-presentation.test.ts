import { describe, expect, it } from "vitest";
import {
  emptyOverlayMemory, presentOverlays, reconcileOverlaySample,
  type SampledOverlay,
} from "../src/overlayPresentation";

const box = [0.2, 0.2, 0.4, 0.65];
const track = (id = "anonymous:1") => ({ id, box, confidence: 0.95 });
const sample = (id: string, at: number, tracks: SampledOverlay[] = [track()]) => ({
  source: "local-camera-0:1", sample: id, capturedAtMs: at, tracks,
});

describe("stable, evidence-honest detection presentation", () => {
  it("keeps a confirmed green box stable between timely AI frames", () => {
    const memory = reconcileOverlaySample(emptyOverlayMemory(), sample("one", 10000), 10300);
    expect(presentOverlays(memory, 10300, 2, 250)[0].state).toBe("confirmed");
    expect(presentOverlays(memory, 11000, 2, 250)[0].state).toBe("confirmed");
    expect(presentOverlays(memory, 11400, 2, 250)[0].state).toBe("confirmed");
    // It becomes amber rather than fading the entire layer on every frame.
    expect(presentOverlays(memory, 11550, 2, 250)[0].state).toBe("last-seen");
    expect(presentOverlays(memory, 12500, 2, 250)).toHaveLength(0);
  });

  it("does not turn repeated WebSocket polls into new evidence", () => {
    const once = reconcileOverlaySample(emptyOverlayMemory(), sample("frame-one", 10000), 10200);
    const polled = reconcileOverlaySample(once, sample("frame-one", 10900), 10900);
    expect(polled).toBe(once);
    expect(polled.tracks[0].confirmedAtMs).toBe(10000);
  });

  it("shows a single missed inference in amber only, then recovers", () => {
    const once = reconcileOverlaySample(emptyOverlayMemory(), sample("one", 10000), 10050);
    const missed = reconcileOverlaySample(once, sample("two", 10500, []), 10550);
    expect(presentOverlays(missed, 10600)[0].state).toBe("last-seen");
    expect(presentOverlays(missed, 11600)).toHaveLength(0);
    const recovered = reconcileOverlaySample(missed, sample("three", 11000), 11050);
    expect(presentOverlays(recovered, 11050)[0].state).toBe("confirmed");
    expect(recovered.tracks[0].visualId).toBe(once.tracks[0].visualId);
  });

  it("bridges an anonymous ID change only when boxes overlap strongly", () => {
    const once = reconcileOverlaySample(emptyOverlayMemory(), sample("one", 10000), 10050);
    const samePlace = reconcileOverlaySample(once, sample("two", 10500, [track("new-id")]), 10550);
    expect(samePlace.tracks[0].visualId).toBe(once.tracks[0].visualId);
    const elsewhere = reconcileOverlaySample(samePlace, sample("three", 11000, [{
      id: "different-person", box: [0.6, 0.2, 0.8, 0.65], confidence: 0.9,
    }]), 11050);
    expect(elsewhere.tracks[0].visualId).not.toBe(once.tracks[0].visualId);
    expect(elsewhere.tracks.find((t) => t.sourceId === "new-id")?.missingAtMs).toBe(11000);
  });

  it("never turns a backend held box into a confirmed green person", () => {
    const memory = reconcileOverlaySample(emptyOverlayMemory(), sample("one", 10000, [{
      ...track(), held: true, held_age_seconds: 0.4,
    }]), 10050);
    expect(presentOverlays(memory, 10050)[0].state).toBe("last-seen");
    expect(presentOverlays(memory, 11200)).toHaveLength(0);
  });

  it("rejects invalid geometry, timestamps and camera-state crossovers", () => {
    const invalid = reconcileOverlaySample(emptyOverlayMemory(), sample("one", 10000, [{
      ...track(), box: [0.1, 0.5, 0.0, 0.7],
    }]), 10050);
    expect(invalid.tracks).toHaveLength(0);
    const valid = reconcileOverlaySample(emptyOverlayMemory(), sample("one", 10000), 10050);
    expect(reconcileOverlaySample(valid, sample("two", 10000), 14000).tracks).toHaveLength(0);
    const changed = reconcileOverlaySample(valid, { ...sample("one", 10500), source: "local-camera-0:2" }, 10550);
    expect(changed.tracks[0].visualId).toBe("visual-1");
    expect(changed.lastSampleAtMs).toBe(10500);
  });
});
