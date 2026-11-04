"""Per-sample visual hints. Never contributes to analytics or counted detections."""

from app.tracking import Track


def build_visual_overlays(
    observed: list[Track],
    track_memory: dict[str, Track],
    capture_time: float,
    *,
    allow_held: bool,
    grace_seconds: float = 0.9,
    limit: int = 64,
) -> list[dict]:
    """Solid = seen this frame; dashed/held = one recently missed sample.

    These transient, session-bound hints must never be passed into counters,
    zone rules, the shift summary or evidence. A held track keeps its old box;
    the UI labels it as unverified and expires it again using its original age.
    """
    overlays = [
        {
            "id": track.id,
            "box": list(track.detection.box),
            "confidence": track.detection.confidence,
            "held": False,
        }
        for track in observed[:limit]
    ]
    if not allow_held:
        return overlays
    observed_ids = {track.id for track in observed}
    for prior in track_memory.values():
        missed_seconds = capture_time - prior.seen
        if (
            prior.id not in observed_ids
            and prior.detection.label == "person"
            and 0 < missed_seconds <= grace_seconds
            and len(overlays) < limit
        ):
            overlays.append(
                {
                    "id": prior.id,
                    "box": list(prior.detection.box),
                    "confidence": prior.detection.confidence,
                    "held": True,
                    "held_age_seconds": round(missed_seconds, 3),
                }
            )
    return overlays
