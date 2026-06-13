"""SQLite schema + data access (ENG-001).

Three tables — ``medications``, ``schedule``, ``events`` — behind a small DAO. Timestamps
are stored as epoch seconds (REAL) for easy range queries; use :func:`iso` to format.
Pass ``":memory:"`` as the path for tests.
"""

from __future__ import annotations

import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

SCHEMA = """
CREATE TABLE IF NOT EXISTS medications (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    name      TEXT NOT NULL UNIQUE,
    class_id  INTEGER,                       -- YOLO class id, may be NULL
    active    INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS schedule (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    med_name    TEXT NOT NULL,
    time_of_day TEXT NOT NULL,               -- "HH:MM" local
    dose        TEXT,
    FOREIGN KEY (med_name) REFERENCES medications(name)
);

CREATE TABLE IF NOT EXISTS events (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    ts        REAL NOT NULL,                 -- epoch seconds
    type      TEXT NOT NULL,                 -- e.g. taken, possible_fall, help_request
    med_name  TEXT,
    detail    TEXT
);

CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
"""


def iso(epoch: float) -> str:
    """Format epoch seconds as a local-time ISO string for display."""
    return datetime.fromtimestamp(epoch).isoformat(timespec="seconds")


def _start_of_today_epoch(now: float | None = None) -> float:
    now = now if now is not None else time.time()
    dt = datetime.fromtimestamp(now)
    return dt.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()


class Database:
    """Thin SQLite DAO for MeSA. Not thread-safe across connections; use one per process."""

    def __init__(self, path: str | Path = "events.db"):
        self.path = str(path)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.init_schema()

    def init_schema(self) -> None:
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    # --- context manager sugar ---
    def __enter__(self) -> "Database":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # --- medications ---
    def add_medication(self, name: str, class_id: int | None = None) -> int:
        cur = self.conn.execute(
            "INSERT OR IGNORE INTO medications(name, class_id) VALUES (?, ?)",
            (name, class_id),
        )
        self.conn.commit()
        if cur.lastrowid:
            return cur.lastrowid
        row = self.conn.execute("SELECT id FROM medications WHERE name = ?", (name,)).fetchone()
        return row["id"]

    def list_medications(self, active_only: bool = True) -> list[sqlite3.Row]:
        sql = "SELECT * FROM medications"
        if active_only:
            sql += " WHERE active = 1"
        return list(self.conn.execute(sql + " ORDER BY name"))

    # --- schedule ---
    def add_schedule(self, med_name: str, time_of_day: str, dose: str | None = None) -> int:
        cur = self.conn.execute(
            "INSERT INTO schedule(med_name, time_of_day, dose) VALUES (?, ?, ?)",
            (med_name, time_of_day, dose),
        )
        self.conn.commit()
        return cur.lastrowid

    def get_schedule(self) -> list[sqlite3.Row]:
        return list(self.conn.execute("SELECT * FROM schedule ORDER BY time_of_day"))

    # --- events ---
    def log_event(
        self,
        type: str,
        med_name: str | None = None,
        detail: str | None = None,
        ts: float | None = None,
    ) -> int:
        ts = ts if ts is not None else time.time()
        cur = self.conn.execute(
            "INSERT INTO events(ts, type, med_name, detail) VALUES (?, ?, ?, ?)",
            (ts, type, med_name, detail),
        )
        self.conn.commit()
        return cur.lastrowid

    def get_events(
        self,
        since: float | None = None,
        types: Iterable[str] | None = None,
        limit: int | None = None,
    ) -> list[sqlite3.Row]:
        sql = "SELECT * FROM events"
        clauses, params = [], []
        if since is not None:
            clauses.append("ts >= ?")
            params.append(since)
        if types is not None:
            types = list(types)
            clauses.append(f"type IN ({','.join('?' * len(types))})")
            params.extend(types)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY ts DESC"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        return list(self.conn.execute(sql, params))

    def meds_taken_today(self, now: float | None = None) -> set[str]:
        """Return the set of med names with a ``taken`` event since local midnight."""
        rows = self.get_events(since=_start_of_today_epoch(now), types=["taken"])
        return {r["med_name"] for r in rows if r["med_name"]}
