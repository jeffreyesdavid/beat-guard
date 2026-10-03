"""Local library of registered beats (a single SQLite file)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

DEFAULT_DB = Path.home() / ".beatguard" / "library.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS tracks (
    id            INTEGER PRIMARY KEY,
    name          TEXT NOT NULL,
    path          TEXT NOT NULL,
    sha256        TEXT NOT NULL UNIQUE,
    duration      REAL NOT NULL,
    registered_at TEXT NOT NULL,
    ots_path      TEXT
);
CREATE TABLE IF NOT EXISTS hashes (
    hash     INTEGER NOT NULL,
    track_id INTEGER NOT NULL REFERENCES tracks(id) ON DELETE CASCADE,
    frame    INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_hash ON hashes(hash);
"""


def connect(path: str | Path = DEFAULT_DB) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def find_by_sha(conn, sha256: str):
    return conn.execute("SELECT * FROM tracks WHERE sha256 = ?", (sha256,)).fetchone()


def add_track(conn, name, path, sha256, duration, registered_at, hashes, ots_path=None) -> int:
    cur = conn.execute(
        "INSERT INTO tracks (name, path, sha256, duration, registered_at, ots_path) VALUES (?,?,?,?,?,?)",
        (name, path, sha256, duration, registered_at, ots_path),
    )
    track_id = cur.lastrowid
    conn.executemany("INSERT INTO hashes (hash, track_id, frame) VALUES (?,?,?)",
                     ((h, track_id, f) for h, f in hashes))
    conn.commit()
    return track_id


def all_tracks(conn):
    return conn.execute("SELECT * FROM tracks ORDER BY id").fetchall()


def lookup(conn, query_hashes):
    """Return rows of (track_id, db_frame, query_frame) for every shared hash."""
    conn.execute("CREATE TEMP TABLE IF NOT EXISTS q (hash INTEGER, frame INTEGER)")
    conn.execute("DELETE FROM q")
    conn.executemany("INSERT INTO q VALUES (?,?)", query_hashes)
    return conn.execute(
        "SELECT h.track_id, h.frame, q.frame FROM q JOIN hashes h ON h.hash = q.hash"
    ).fetchall()
