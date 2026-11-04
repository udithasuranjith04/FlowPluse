import json
import sqlite3
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.schemas import ZoneConfig


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS configurations (camera_id TEXT PRIMARY KEY, data TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS events (
            id TEXT PRIMARY KEY, camera_id TEXT NOT NULL, type TEXT NOT NULL,
            state TEXT NOT NULL, review_status TEXT NOT NULL, started_at TEXT NOT NULL,
            data TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS events_time ON events(started_at DESC);
        CREATE INDEX IF NOT EXISTS events_camera ON events(camera_id, type, review_status);
        CREATE TABLE IF NOT EXISTS shift_preferences (
            name TEXT PRIMARY KEY, enabled INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS shift_summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT, camera_id TEXT NOT NULL,
            created_at TEXT NOT NULL, region TEXT NOT NULL,
            processed_samples INTEGER NOT NULL, elapsed_seconds REAL NOT NULL,
            average_visible REAL NOT NULL, peak_visible INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS shift_summaries_recent ON shift_summaries(camera_id, created_at);
        """)
        self.db.commit()

    def get_config(self, camera_id: str, default: ZoneConfig) -> ZoneConfig:
        with self.lock:
            row = self.db.execute(
                "SELECT data FROM configurations WHERE camera_id=?", (camera_id,)
            ).fetchone()
        return ZoneConfig.model_validate_json(row[0]) if row else default

    def save_config(self, camera_id: str, config: ZoneConfig) -> None:
        with self.lock, self.db:
            self.db.execute(
                "INSERT INTO configurations VALUES (?, ?) ON CONFLICT(camera_id) "
                "DO UPDATE SET data=excluded.data",
                (camera_id, config.model_dump_json()),
            )

    def put_event(self, event: dict) -> dict:
        with self.lock, self.db:
            old = self.db.execute(
                "SELECT review_status FROM events WHERE id=?", (event["id"],)
            ).fetchone()
            if old:
                event = {**event, "review_status": old[0]}
            self.db.execute(
                "INSERT INTO events VALUES (?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET state=excluded.state, "
                "review_status=excluded.review_status, data=excluded.data",
                (
                    event["id"],
                    event["camera_id"],
                    event["type"],
                    event["state"],
                    event["review_status"],
                    event["started_at"],
                    json.dumps(event),
                ),
            )
        return event

    def event(self, event_id: str) -> dict | None:
        with self.lock:
            row = self.db.execute("SELECT data FROM events WHERE id=?", (event_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def review(self, event_id: str, status: str) -> dict | None:
        with self.lock, self.db:
            event = self.event(event_id)
            if not event:
                return None
            event["review_status"] = status
            self.db.execute(
                "UPDATE events SET review_status=?, data=? WHERE id=?",
                (status, json.dumps(event), event_id),
            )
        return event

    def events(self, *, limit: int = 50, offset: int = 0, **filters) -> dict:
        clauses, values = [], []
        for key in ("camera_id", "type", "review_status", "state"):
            if filters.get(key):
                clauses.append(f"{key}=?")
                values.append(filters[key])
        domain = filters.get("domain")
        if domain == "people":
            clauses.append("type IN (?, ?)")
            values.extend(["extended_dwell", "possible_queue_buildup"])
        elif domain == "legacy":
            clauses.append("type IN (?, ?)")
            values.extend(["potential_stopped_vehicle", "congestion_buildup"])
        for key, op in (("since", ">="), ("until", "<=")):
            if filters.get(key):
                clauses.append(f"started_at{op}?")
                values.append(filters[key])
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with self.lock:
            total = self.db.execute("SELECT count(*) FROM events" + where, values).fetchone()[0]
            rows = self.db.execute(
                "SELECT data FROM events" + where + " ORDER BY started_at DESC LIMIT ? OFFSET ?",
                [*values, limit, offset],
            ).fetchall()
        return {
            "items": [json.loads(row[0]) for row in rows],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    def resolve_interrupted(self, timestamp: str) -> None:
        """Active observations cannot survive a worker/process/session discontinuity."""
        for event in self.events(state="active", limit=10000)["items"]:
            event.update(state="resolved", ended_at=timestamp)
            event["quality_flags"] = list(set(event["quality_flags"] + ["session_ended"]))
            self.put_event(event)

    def shift_memory_enabled(self) -> bool:
        with self.lock:
            row = self.db.execute(
                "SELECT enabled FROM shift_preferences WHERE name='shift_memory'"
            ).fetchone()
            return bool(row[0]) if row else False

    def set_shift_memory(self, enabled: bool) -> None:
        with self.lock, self.db:
            self.db.execute(
                "INSERT INTO shift_preferences(name,enabled) VALUES ('shift_memory',?) "
                "ON CONFLICT(name) DO UPDATE SET enabled=excluded.enabled",
                (int(enabled),),
            )
            if not enabled:
                self.db.execute("DELETE FROM shift_summaries")

    def archive_shift(self, camera_id: str, region: str, summary: dict) -> bool:
        # Short sessions are not a useful baseline for an operating shift.
        # These are quality minimums, not a promise of statistical validity.
        if (
            not self.shift_memory_enabled()
            or summary.get("processed_samples", 0) < 300
            or summary.get("elapsed_seconds", 0) < 240
            or summary.get("average_visible") is None
        ):
            return False
        now = datetime.now(UTC)
        with self.lock, self.db:
            self.db.execute(
                "INSERT INTO shift_summaries(camera_id,created_at,region,processed_samples,"
                "elapsed_seconds,average_visible,peak_visible) VALUES (?,?,?,?,?,?,?)",
                (
                    camera_id,
                    now.isoformat(),
                    region,
                    summary["processed_samples"],
                    summary["elapsed_seconds"],
                    summary["average_visible"],
                    summary["peak_visible"],
                ),
            )
            self.db.execute(
                "DELETE FROM shift_summaries WHERE created_at < ?",
                ((now - timedelta(days=30)).isoformat(),),
            )
            # Bounded archive even if owner monitors many sessions in a day.
            self.db.execute(
                "DELETE FROM shift_summaries WHERE id NOT IN "
                "(SELECT id FROM shift_summaries ORDER BY id DESC LIMIT 60)"
            )
        return True

    def saved_shifts(self, camera_id: str, region: str) -> list[dict]:
        if not self.shift_memory_enabled():
            return []
        with self.lock:
            rows = self.db.execute(
                "SELECT created_at, processed_samples, elapsed_seconds, "
                "average_visible, peak_visible FROM shift_summaries "
                "WHERE camera_id=? AND region=? AND created_at>=? "
                "AND processed_samples>=300 AND elapsed_seconds>=240 "
                "ORDER BY created_at DESC LIMIT 30",
                (camera_id, region, (datetime.now(UTC) - timedelta(days=30)).isoformat()),
            ).fetchall()
        return [dict(row) for row in rows]

    def close(self) -> None:
        with self.lock:
            self.db.close()
