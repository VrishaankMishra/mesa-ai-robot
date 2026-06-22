"""SQLite schema + data access (ENG-001).

Core tables — ``medications``, ``schedule``, ``events`` — behind a small DAO. Timestamps
are stored as epoch seconds (REAL) for easy range queries; use :func:`iso` to format.
Pass ``":memory:"`` as the path for tests.

The research-extension tables ``sessions`` and ``clips`` (DATA-002 / DATA-001 / RES-001)
are additive: the heavy per-frame feature arrays live in on-disk ``.npz`` files, and a
``clips`` row is the catalog entry pointing at one. See ``docs/research-dataset-design.md``.
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
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

-- --- research extension (DATA-002 / DATA-001 / RES-001) ---
CREATE TABLE IF NOT EXISTS sessions (
    id              TEXT PRIMARY KEY,           -- uuid4 hex
    participant     TEXT,                        -- pseudonymous id, never a real name
    tier            INTEGER NOT NULL,            -- 1 self / 2 consented participants / 3 deployed home
    consent_flag    INTEGER NOT NULL DEFAULT 0,  -- tier >= 2 requires 1 (enforced in DAO)
    consent_version TEXT,
    conditions      TEXT,                        -- JSON: lighting, distance_m, n_bottles, notes
    fps             REAL,
    started_at      REAL NOT NULL,               -- epoch seconds
    ended_at        REAL
);

CREATE TABLE IF NOT EXISTS clips (
    id              TEXT PRIMARY KEY,            -- uuid4 hex
    session_id      TEXT NOT NULL REFERENCES sessions(id),
    path            TEXT NOT NULL,               -- relative path to the .npz feature file
    anchor_ts       REAL,                        -- epoch of the taken/contact event (NULL = negative)
    anchor_event_id INTEGER REFERENCES events(id),
    window_seconds  REAL NOT NULL,               -- buffered window length actually stored
    n_frames        INTEGER NOT NULL,
    label_a         TEXT NOT NULL,               -- 'interact' | 'no_interaction'
    label_b         TEXT,                        -- med_name; NULL for negatives / unknown bottle
    label_source    TEXT NOT NULL DEFAULT 'auto',-- 'auto' | 'manual'
    review_status   TEXT NOT NULL DEFAULT 'auto',-- 'auto' | 'confirmed' | 'relabeled' | 'discarded'
    split           TEXT,                         -- 'train' | 'val' | 'test' (set at packaging)
    created_at      REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_clips_session ON clips(session_id);
CREATE INDEX IF NOT EXISTS idx_clips_label   ON clips(label_a, review_status);
"""

# Label / review vocabularies (kept here so callers and the review view agree).
LABEL_A_VALUES = ("interact", "no_interaction")
REVIEW_STATUSES = ("auto", "confirmed", "relabeled", "discarded")


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

    # --- research: sessions (DATA-002) ---
    def create_session(
        self,
        tier: int,
        participant: str | None = None,
        consent_flag: bool = False,
        consent_version: str | None = None,
        conditions: dict | str | None = None,
        fps: float | None = None,
        started_at: float | None = None,
    ) -> str:
        """Open a collection session; returns its uuid4-hex id.

        Enforces the privacy invariant: Tier 2/3 collection (real participants) requires
        ``consent_flag=True``. ``conditions`` may be a dict (stored as JSON) or a string.
        """
        if tier not in (1, 2, 3):
            raise ValueError(f"tier must be 1, 2, or 3 (got {tier!r})")
        if tier >= 2 and not consent_flag:
            raise ValueError("tier >= 2 requires consent_flag=True (DATA-002 privacy invariant)")
        if isinstance(conditions, dict):
            conditions = json.dumps(conditions)
        session_id = uuid.uuid4().hex
        started_at = started_at if started_at is not None else time.time()
        self.conn.execute(
            "INSERT INTO sessions(id, participant, tier, consent_flag, consent_version, "
            "conditions, fps, started_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (session_id, participant, tier, int(consent_flag), consent_version,
             conditions, fps, started_at),
        )
        self.conn.commit()
        return session_id

    def end_session(self, session_id: str, ended_at: float | None = None) -> None:
        """Mark a session finished (sets ``ended_at``)."""
        ended_at = ended_at if ended_at is not None else time.time()
        self.conn.execute(
            "UPDATE sessions SET ended_at = ? WHERE id = ?", (ended_at, session_id)
        )
        self.conn.commit()

    def get_session(self, session_id: str) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()

    # --- research: clips (DATA-001 / RES-001) ---
    def add_clip(
        self,
        session_id: str,
        path: str,
        window_seconds: float,
        n_frames: int,
        label_a: str,
        label_b: str | None = None,
        anchor_ts: float | None = None,
        anchor_event_id: int | None = None,
        label_source: str = "auto",
        review_status: str = "auto",
        created_at: float | None = None,
    ) -> str:
        """Catalog one labeled clip (its features live in the ``.npz`` at ``path``).

        Returns the clip's uuid4-hex id. Validates ``label_a`` / ``review_status`` against
        the known vocabularies so the review view and writers can't drift apart.
        """
        if label_a not in LABEL_A_VALUES:
            raise ValueError(f"label_a must be one of {LABEL_A_VALUES} (got {label_a!r})")
        if review_status not in REVIEW_STATUSES:
            raise ValueError(f"review_status must be one of {REVIEW_STATUSES} (got {review_status!r})")
        clip_id = uuid.uuid4().hex
        created_at = created_at if created_at is not None else time.time()
        self.conn.execute(
            "INSERT INTO clips(id, session_id, path, anchor_ts, anchor_event_id, "
            "window_seconds, n_frames, label_a, label_b, label_source, review_status, "
            "created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (clip_id, session_id, path, anchor_ts, anchor_event_id, window_seconds,
             n_frames, label_a, label_b, label_source, review_status, created_at),
        )
        self.conn.commit()
        return clip_id

    def update_clip_review(
        self,
        clip_id: str,
        review_status: str,
        label_b: str | None = None,
    ) -> None:
        """Apply a reviewer's decision (DATA-003).

        Passing ``label_b`` relabels the clip and marks ``label_source='manual'``; this is
        the ``relabeled`` path. ``confirmed`` / ``discarded`` just set the status.
        """
        if review_status not in REVIEW_STATUSES:
            raise ValueError(f"review_status must be one of {REVIEW_STATUSES} (got {review_status!r})")
        if label_b is not None:
            self.conn.execute(
                "UPDATE clips SET review_status = ?, label_b = ?, label_source = 'manual' "
                "WHERE id = ?",
                (review_status, label_b, clip_id),
            )
        else:
            self.conn.execute(
                "UPDATE clips SET review_status = ? WHERE id = ?", (review_status, clip_id)
            )
        self.conn.commit()

    def get_clips(
        self,
        session_id: str | None = None,
        label_a: str | None = None,
        review_status: str | None = None,
        split: str | None = None,
    ) -> list[sqlite3.Row]:
        """Query the clip catalog, oldest first. All filters are optional and ANDed."""
        sql = "SELECT * FROM clips"
        clauses, params = [], []
        for col, val in (("session_id", session_id), ("label_a", label_a),
                         ("review_status", review_status), ("split", split)):
            if val is not None:
                clauses.append(f"{col} = ?")
                params.append(val)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY created_at"
        return list(self.conn.execute(sql, params))
