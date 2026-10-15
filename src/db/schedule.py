"""Data access for effective-dated work schedules (v26).

One row per change: the schedule for a date is the latest period whose
``effective_from`` is <= that date. ``settings.schedule_start/end`` are kept
as a mirror of the latest period for backward compatibility.
"""
import sqlite3
from datetime import UTC, datetime

from src.config import (DEFAULT_SCHEDULE_END, DEFAULT_SCHEDULE_START,
                        OLD_SCHEDULE_END, OLD_SCHEDULE_START,
                        SCHEDULE_CUTOVER_DATE)
from src.db.settings import set_setting


def list_periods(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT id, effective_from, start_time, end_time, created_at "
        "FROM schedule_periods ORDER BY effective_from ASC"
    ).fetchall()
    return [dict(r) for r in rows]


def schedule_for(conn: sqlite3.Connection, tanggal: str) -> tuple[str, str]:
    """(start, end) dot-format untuk tanggal; fallback default aplikasi."""
    row = conn.execute(
        "SELECT start_time, end_time FROM schedule_periods "
        "WHERE effective_from <= ? ORDER BY effective_from DESC LIMIT 1",
        (tanggal,),
    ).fetchone()
    if row:
        return row["start_time"], row["end_time"]
    return DEFAULT_SCHEDULE_START, DEFAULT_SCHEDULE_END


def current_schedule(conn: sqlite3.Connection) -> tuple[str, str]:
    return schedule_for(conn, datetime.now(UTC).date().isoformat())


def ensure_historical_schedule(conn: sqlite3.Connection, *,
                               extra_dates=()) -> bool:
    """Pecah periode default (09.00-17.00 sejak 1970) bila ada data historis.

    Database hasil instalasi baru (v26) hanya punya SATU periode default
    09.00-17.00 sejak 1970 — padahal datanya bisa berisi tanggal sebelum
    cutoff 14 Sep 2026 yang masih memakai jam mesin lama 08.00-16.00.
    Bila ada baris absensi (atau tanggal import yang akan masuk lewat
    ``extra_dates``) sebelum cutoff, periode dipecah menjadi
    1970-01-01 08.00-16.00 + cutoff 09.00-17.00. DB dengan >= 2 periode
    atau jadwal custom tidak disentuh. Idempoten.

    Return True bila periode baru saja dipecah.
    """
    periods = conn.execute(
        "SELECT id, effective_from, start_time, end_time "
        "FROM schedule_periods ORDER BY effective_from ASC"
    ).fetchall()
    if len(periods) != 1:
        return False
    only = periods[0]
    if (only["effective_from"] != "1970-01-01"
            or only["start_time"] != DEFAULT_SCHEDULE_START
            or only["end_time"] != DEFAULT_SCHEDULE_END):
        return False
    has_old = conn.execute(
        "SELECT 1 FROM attendance_records WHERE tanggal < ? LIMIT 1",
        (SCHEDULE_CUTOVER_DATE,),
    ).fetchone() is not None
    if not has_old and not any(
            d and d < SCHEDULE_CUTOVER_DATE for d in extra_dates):
        return False
    now = datetime.now(UTC).isoformat(timespec="seconds")
    conn.execute(
        "UPDATE schedule_periods SET start_time = ?, end_time = ? WHERE id = ?",
        (OLD_SCHEDULE_START, OLD_SCHEDULE_END, only["id"]),
    )
    conn.execute(
        "INSERT INTO schedule_periods "
        "(effective_from, start_time, end_time, created_at) VALUES (?,?,?,?)",
        (SCHEDULE_CUTOVER_DATE, DEFAULT_SCHEDULE_START,
         DEFAULT_SCHEDULE_END, now),
    )
    return True


def add_period(conn: sqlite3.Connection, *, effective_from: str,
               start: str, end: str) -> None:
    now = datetime.now(UTC).isoformat(timespec="seconds")
    conn.execute(
        "INSERT INTO schedule_periods "
        "(effective_from, start_time, end_time, created_at) VALUES (?,?,?,?)",
        (effective_from, start, end, now),
    )
    _mirror_latest(conn)


def delete_period(conn: sqlite3.Connection, period_id: int) -> None:
    conn.execute("DELETE FROM schedule_periods WHERE id = ?", (period_id,))
    _mirror_latest(conn)


def _mirror_latest(conn: sqlite3.Connection) -> None:
    latest = conn.execute(
        "SELECT start_time, end_time FROM schedule_periods "
        "ORDER BY effective_from DESC LIMIT 1"
    ).fetchone()
    if latest:
        set_setting(conn, "schedule_start", latest["start_time"])
        set_setting(conn, "schedule_end", latest["end_time"])
