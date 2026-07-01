"""'Sudah dihubungi' WhatsApp contact marks, per employee/month.

Mirrors src/db/coaching.py: presence of a row = contacted for that month.
Scoped to (employee_id, year_month) so a new active month starts clean.
"""
import sqlite3
from datetime import datetime, UTC


def mark_contacted(conn: sqlite3.Connection, *, employee_id: int,
                   year_month: str, contacted_at: str | None = None) -> None:
    """Insert/refresh the contact mark (UPSERT). contacted_at defaults to now."""
    ts = contacted_at or datetime.now(UTC).isoformat(timespec="seconds")
    conn.execute(
        """
        INSERT INTO wa_contacts (employee_id, year_month, contacted_at)
        VALUES (?, ?, ?)
        ON CONFLICT (employee_id, year_month)
            DO UPDATE SET contacted_at = excluded.contacted_at
        """,
        (employee_id, year_month, ts),
    )


def unmark_contacted(conn: sqlite3.Connection, *, employee_id: int,
                     year_month: str) -> None:
    conn.execute(
        "DELETE FROM wa_contacts WHERE employee_id = ? AND year_month = ?",
        (employee_id, year_month),
    )


def is_contacted(conn: sqlite3.Connection, *, employee_id: int,
                 year_month: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM wa_contacts WHERE employee_id = ? AND year_month = ?",
        (employee_id, year_month),
    ).fetchone()
    return row is not None


def contacted_map(conn: sqlite3.Connection, year_month: str) -> dict:
    """{employee_id: contacted_at} for the given month."""
    rows = conn.execute(
        "SELECT employee_id, contacted_at FROM wa_contacts WHERE year_month = ?",
        (year_month,),
    ).fetchall()
    return {r["employee_id"]: r["contacted_at"] for r in rows}
