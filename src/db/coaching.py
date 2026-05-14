"""Coaching session CRUD + list query for the Coaching screen.

A coaching session row exists when an employee has been marked as coached for
a given week. Absence of a row = "Belum coached". Notes are optional.
"""
import sqlite3
from datetime import datetime, UTC
from typing import List, Optional

from src.config import COACHING_EXCLUDED
from src.db.outlier import excluded_employee_ids, exclusion_sql


def mark_coached(
    conn: sqlite3.Connection,
    *,
    employee_id: int,
    week_start: str,
    notes: Optional[str] = None,
) -> None:
    """Insert or update a coaching session (UPSERT). Idempotent.

    coached_at is always set to now() on insert. On conflict (same employee
    + same week), only notes is overwritten — coached_at preserved.
    """
    now = datetime.now(UTC).isoformat(timespec="seconds")
    conn.execute(
        """
        INSERT INTO coaching_sessions (employee_id, week_start, coached_at, notes)
        VALUES (?, ?, ?, ?)
        ON CONFLICT (employee_id, week_start) DO UPDATE SET
            notes = excluded.notes
        """,
        (employee_id, week_start, now, notes),
    )


def unmark_coached(
    conn: sqlite3.Connection,
    *,
    employee_id: int,
    week_start: str,
) -> None:
    """Delete a coaching session — toggles Sudah back to Belum."""
    conn.execute(
        "DELETE FROM coaching_sessions WHERE employee_id = ? AND week_start = ?",
        (employee_id, week_start),
    )


def get_coaching_notes(
    conn: sqlite3.Connection,
    *,
    employee_id: int,
    week_start: str,
) -> Optional[str]:
    """Return notes for the session, or None if no session exists."""
    row = conn.execute(
        "SELECT notes FROM coaching_sessions WHERE employee_id = ? AND week_start = ?",
        (employee_id, week_start),
    ).fetchone()
    return row["notes"] if row else None


def update_notes(
    conn: sqlite3.Connection,
    *,
    employee_id: int,
    week_start: str,
    notes: Optional[str],
) -> None:
    """Update notes on an existing session (no-op if session doesn't exist)."""
    conn.execute(
        """
        UPDATE coaching_sessions
           SET notes = ?
         WHERE employee_id = ? AND week_start = ?
        """,
        (notes, employee_id, week_start),
    )


def list_coaching_for_week(
    conn: sqlite3.Connection,
    *,
    week_start: str,
    week_end: str,
    threshold_minutes: int = 75,
) -> List[sqlite3.Row]:
    """Return pegawai over the lateness threshold in given week, with status.

    Lateness aggregation mirrors src/core/insights.py — uses the same
    `COACHING_EXCLUDED` tuple from `src.config` for work-justified categories
    so the two stay in lockstep:
      - Requires masuk IS NOT NULL (employee must have clocked in)
      - Excludes work-justified categories

    LEFT JOIN with coaching_sessions to flag is_coached.

    Returns sqlite3.Row with columns:
      - employee_id, nama, dept, no_staff
      - total_terlambat (int, minutes)
      - week_start (echo)
      - coached_at (str ISO datetime, or NULL)
      - is_coached (1 or 0)
    """
    placeholders = ",".join("?" for _ in COACHING_EXCLUDED)
    excluded = excluded_employee_ids(conn, week_start[:7])
    exc_frag, exc_params = exclusion_sql(excluded, column="ar.employee_id")
    sql = f"""
        WITH terlambat AS (
            SELECT
                ar.employee_id,
                SUM(CASE
                    WHEN ar.reason_category IN ({placeholders}) THEN 0
                    WHEN ar.masuk IS NULL THEN 0
                    ELSE COALESCE(ar.terlambat_menit, 0)
                END) AS total_terlambat
              FROM attendance_records ar
             WHERE ar.tanggal BETWEEN ? AND ?{exc_frag}
             GROUP BY ar.employee_id
        )
        SELECT
            t.employee_id,
            e.nama,
            e.dept,
            e.no_staff,
            t.total_terlambat,
            ? AS week_start,
            cs.coached_at,
            CASE WHEN cs.id IS NOT NULL THEN 1 ELSE 0 END AS is_coached
          FROM terlambat t
          JOIN employees e ON t.employee_id = e.id
          LEFT JOIN coaching_sessions cs
                 ON cs.employee_id = t.employee_id
                AND cs.week_start = ?
         WHERE t.total_terlambat > ?
         ORDER BY t.total_terlambat DESC, e.nama ASC
    """
    params = (
        *COACHING_EXCLUDED, week_start, week_end, *exc_params,
        week_start, week_start, threshold_minutes,
    )
    return conn.execute(sql, params).fetchall()
