"""
SQLite persistence — the app's only stateful store.

Everything else in the backend is stateless (recomputed from Garmin/sample data
on each request). Two things genuinely need to persist across restarts and belong
here:

  1. **Strength working weights.** The exercise catalog (names, schemes, %1RM) is
     fixed reference data seeded from `strength_catalog.json`, but the weight the
     athlete actually lifts is personal, editable, and starts empty — they fill it
     in over time. That's a stored, mutable value.
  2. **Workout completion log.** Which planned sessions actually got done, so the
     dashboard/coach can show adherence rather than just the prescription.

Plain `sqlite3` (stdlib) — no ORM. The schema is small and the queries are simple;
an ORM would be more machinery than this earns.
"""

import json
import sqlite3
from pathlib import Path

_DB_PATH = Path(__file__).parent / "cadence.db"
_CATALOG_PATH = Path(__file__).parent / "strength_catalog.json"


def _connect():
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row          # rows behave like dicts
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def load_catalog() -> dict:
    """The static exercise catalog + condensed-session mapping (from JSON)."""
    return json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))


def init_db():
    """Create tables if needed and seed the exercise catalog once.

    Idempotent: safe to call on every startup. Seeding only runs when the
    `exercise` table is empty, so a user's entered weights are never clobbered.
    """
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS exercise (
                id                INTEGER PRIMARY KEY,
                day_label         TEXT NOT NULL,
                name              TEXT NOT NULL,
                scheme            TEXT,
                pct_1rm           INTEGER,
                is_compound       INTEGER NOT NULL DEFAULT 0,
                working_weight_kg REAL           -- NULL until the athlete fills it in
            );

            CREATE TABLE IF NOT EXISTS workout_log (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                date       TEXT NOT NULL,          -- ISO date of the session
                title      TEXT NOT NULL,
                kind       TEXT,                   -- run | strength | cross | ...
                completed  INTEGER NOT NULL DEFAULT 1,
                notes      TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            """
        )
        already = conn.execute("SELECT COUNT(*) AS n FROM exercise").fetchone()["n"]
        if already == 0:
            catalog = load_catalog()
            conn.executemany(
                """INSERT INTO exercise (id, day_label, name, scheme, pct_1rm, is_compound)
                   VALUES (:id, :day_label, :name, :scheme, :pct_1rm, :is_compound)""",
                [
                    {**e, "is_compound": 1 if e["is_compound"] else 0}
                    for e in catalog["exercises"]
                ],
            )


# ---- strength catalog + weights ----

def list_exercises() -> list:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM exercise ORDER BY id"
        ).fetchall()
    return [dict(r) for r in rows]


def set_working_weight(exercise_id: int, weight_kg):
    """Set (or clear, with None) the working weight for one exercise.

    Returns the updated row, or None if the id doesn't exist.
    """
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE exercise SET working_weight_kg = ? WHERE id = ?",
            (weight_kg, exercise_id),
        )
        if cur.rowcount == 0:
            return None
        row = conn.execute("SELECT * FROM exercise WHERE id = ?", (exercise_id,)).fetchone()
    return dict(row)


def condensed_sessions() -> dict:
    """The 2-day condensed split as {session_label: [full exercise rows]}.

    Joins the curated id lists in the catalog against the DB rows so each lift
    carries its current working weight.
    """
    catalog = load_catalog()
    by_id = {e["id"]: e for e in list_exercises()}
    out = {}
    for label, ids in catalog["condensed_sessions"].items():
        out[label] = [by_id[i] for i in ids if i in by_id]
    return out


# ---- workout log ----

def log_workout(date: str, title: str, kind: str = None,
                completed: bool = True, notes: str = None) -> dict:
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO workout_log (date, title, kind, completed, notes)
               VALUES (?, ?, ?, ?, ?)""",
            (date, title, kind, 1 if completed else 0, notes),
        )
        row = conn.execute(
            "SELECT * FROM workout_log WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
    return dict(row)


def list_logs(since: str = None) -> list:
    query = "SELECT * FROM workout_log"
    params = ()
    if since:
        query += " WHERE date >= ?"
        params = (since,)
    query += " ORDER BY date DESC, id DESC"
    with _connect() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]
