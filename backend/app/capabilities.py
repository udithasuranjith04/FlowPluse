"""Source capabilities describe what evidence a transport can provide."""


def capabilities(kind: str, authorized: bool) -> dict[str, bool]:
    snapshot = kind in {"snapshot", "digitraffic", "digitraffic_snapshot"}
    return {
        "continuous_video": not snapshot,
        "snapshot_only": snapshot,
        "supports_tracking": not snapshot and authorized,
        "supports_temporal_events": not snapshot and authorized,
        # Local/video receipt time is not a hardware/provider capture timestamp.
        "capture_timestamp_available": False,
        "source_authorized": authorized,
    }
