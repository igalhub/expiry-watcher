import sqlite3
from datetime import datetime, timezone
from typing import Optional

_SCHEMA = """
CREATE TABLE IF NOT EXISTS results (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL,
    type          TEXT    NOT NULL,
    days_remaining REAL,
    severity      TEXT,
    checked_at    TEXT    NOT NULL,
    error         TEXT,
    UNIQUE(name, type)
);

CREATE TABLE IF NOT EXISTS metadata (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def init_db(path: str) -> None:
    with sqlite3.connect(path) as conn:
        conn.executescript(_SCHEMA)


def write_results(path: str, results: list[dict]) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(path) as conn:
        for r in results:
            conn.execute(
                """
                INSERT INTO results (name, type, days_remaining, severity, checked_at, error)
                VALUES (:name, :type, :days_remaining, :severity, :checked_at, :error)
                ON CONFLICT(name, type) DO UPDATE SET
                    days_remaining = excluded.days_remaining,
                    severity       = excluded.severity,
                    checked_at     = excluded.checked_at,
                    error          = excluded.error
                """,
                {
                    "name":           r["name"],
                    "type":           r["type"],
                    "days_remaining": r.get("days_remaining"),
                    "severity":       r.get("severity"),
                    "checked_at":     r.get("checked_at") or now,
                    "error":          r.get("error"),
                },
            )
        conn.execute(
            "INSERT INTO metadata (key, value) VALUES ('last_checked', ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (now,),
        )


def read_results(path: str) -> list[dict]:
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT name, type, days_remaining, severity, checked_at, error FROM results"
        ).fetchall()
    return [dict(row) for row in rows]


def get_last_checked(path: str) -> Optional[datetime]:
    with sqlite3.connect(path) as conn:
        row = conn.execute(
            "SELECT value FROM metadata WHERE key = 'last_checked'"
        ).fetchone()
    if row is None:
        return None
    return datetime.fromisoformat(row[0])
