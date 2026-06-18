"""SQLite storage. The database file is persistent and lives outside the
code directory; WAL mode keeps concurrent reads/writes smooth under gunicorn.
"""
import sqlite3
from pathlib import Path

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS invites (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    token        TEXT UNIQUE NOT NULL,
    created_at   TEXT NOT NULL,
    response     TEXT,            -- 'accept' | 'decline' | NULL
    guest_name   TEXT,
    responded_at TEXT
);

CREATE TABLE IF NOT EXISTS login_attempts (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    ip      TEXT NOT NULL,
    ts      TEXT NOT NULL,
    success INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_attempts_ip_ts ON login_attempts(ip, ts);
CREATE INDEX IF NOT EXISTS idx_invites_id      ON invites(id);
"""


def connect():
    Path(config.DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_db():
    conn = connect()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()
