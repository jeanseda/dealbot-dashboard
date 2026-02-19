"""
Database abstraction layer.
- Development: SQLite (via DEAL_TRACKER_DB path)
- Production:  PostgreSQL (via DATABASE_URL)
"""

import os
from contextlib import contextmanager
from pathlib import Path

DATABASE_URL = os.getenv("DATABASE_URL", "")

# Render uses postgres:// but psycopg2 needs postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

USE_POSTGRES = bool(DATABASE_URL)


# ── Connection factory ────────────────────────────────────────────────────────

if USE_POSTGRES:
    import psycopg2
    import psycopg2.extras

    @contextmanager
    def get_db():
        conn = psycopg2.connect(DATABASE_URL)
        try:
            yield conn
        finally:
            conn.close()

    P = "%s"  # PostgreSQL placeholder

    def _fetchone(cursor):
        row = cursor.fetchone()
        if row is None:
            return None
        cols = [desc[0] for desc in cursor.description]
        return dict(zip(cols, row))

    def _fetchall(cursor):
        rows = cursor.fetchall()
        if not rows:
            return []
        cols = [desc[0] for desc in cursor.description]
        return [dict(zip(cols, row)) for row in rows]

else:
    import sqlite3

    DB_PATH = Path(
        os.getenv(
            "DEAL_TRACKER_DB",
            str(Path.home() / ".openclaw/workspace/deal-tracker/deal_tracker.db"),
        )
    )

    @contextmanager
    def get_db():
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    P = "?"  # SQLite placeholder

    def _fetchone(cursor):
        row = cursor.fetchone()
        return dict(row) if row else None

    def _fetchall(cursor):
        rows = cursor.fetchall()
        return [dict(r) for r in rows]


# ── Query helpers ─────────────────────────────────────────────────────────────

def db_fetchone(conn, sql: str, params: tuple = ()):
    """Execute a SELECT and return first row as dict (or None)."""
    cur = conn.cursor()
    cur.execute(sql, params)
    return _fetchone(cur)


def db_fetchall(conn, sql: str, params: tuple = ()):
    """Execute a SELECT and return all rows as list of dicts."""
    cur = conn.cursor()
    cur.execute(sql, params)
    return _fetchall(cur)


def db_execute(conn, sql: str, params: tuple = ()):
    """Execute INSERT/UPDATE/DELETE and commit."""
    cur = conn.cursor()
    cur.execute(sql, params)
    conn.commit()
