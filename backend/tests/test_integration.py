from app.rules import RuleEngine
from app.schemas import demo_zones
from app.synthetic import render_frame
from app.tracking import Tracker
from app.vision import SyntheticDetector


def test_generated_pixels_to_detector_tracker_rules_sqlite_api(client):
    detector, tracker = SyntheticDetector(), Tracker()
    engine = RuleEngine("demo", demo_zones(), "REPLAY", detector.name)
    events = {}
    for i in range(160):
        t = i * 0.5
        tracks = tracker.update(detector.detect(render_frame(t)), t)
        for event in engine.step(tracks, t):
            client.app.state.store.put_event(event)
            events[event["id"]] = event
    assert {e["type"] for e in events.values()} == {
        "potential_stopped_vehicle",
        "congestion_buildup",
    }
    response = client.get("/api/events").json()
    assert response["total"] == len(events)
    assert all(e["source_mode"] == "REPLAY" for e in response["items"])
