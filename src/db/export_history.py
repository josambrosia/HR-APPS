"""Repo functions for export_history table.

Tracks each successful Laporan Bulanan export so the UI can show
'Riwayat Export Terakhir' history list.
"""
import sqlite3


def record_export(
    conn: sqlite3.Connection,
    *,
    out_path: str,
    template: str,
    year_month: str,
    filled: int,
    na: int,
    not_found: int,
    created_at: str | None = None,
) -> int:
    """Insert a row for a completed export. Returns the new row id.

    Caller is responsible for transaction commit via the get_connection()
    context manager — no explicit conn.commit() here (matches the other
    repo modules in src/db/).

    If created_at is not provided, defaults to current UTC ISO-8601
    timestamp (matches imported_at format in attendance_records).
    """
    from datetime import datetime, timezone
    if created_at is None:
        created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    cur = conn.execute(
        """
        INSERT INTO export_history
            (out_path, template, year_month, filled, na, not_found, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (out_path, template, year_month, filled, na, not_found, created_at),
    )
    return cur.lastrowid


def list_recent_exports(
    conn: sqlite3.Connection, limit: int = 5,
) -> list[dict]:
    """Return the most-recent exports, newest first.

    Each dict has keys: id, out_path, template, year_month, filled,
    na, not_found, created_at.
    """
    rows = conn.execute(
        """
        SELECT id, out_path, template, year_month, filled, na, not_found, created_at
        FROM export_history
        ORDER BY created_at DESC, id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]
