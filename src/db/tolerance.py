"""Data access for effective-dated late tolerance (v26).

Perubahan toleransi berlaku mulai tanggal tertentu; tanggal sebelumnya tetap
memakai nilai lama sehingga warna/status bulan lama tidak ikut berubah.
``settings.late_tolerance_min`` dijaga sebagai cermin nilai terbaru untuk
kompatibilitas pembaca lama.
"""
import sqlite3
from datetime import UTC, datetime

from src.config import DEFAULT_LATE_TOLERANCE_MIN
from src.db.settings import get_setting, set_setting


def list_periods(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT id, effective_from, tolerance_min, created_at "
        "FROM tolerance_periods ORDER BY effective_from ASC"
    ).fetchall()
    return [dict(r) for r in rows]


def tolerance_for(conn: sqlite3.Connection, tanggal: str) -> int:
    """Toleransi (menit) yang berlaku pada tanggal; fallback setelan lama."""
    row = conn.execute(
        "SELECT tolerance_min FROM tolerance_periods "
        "WHERE effective_from <= ? ORDER BY effective_from DESC LIMIT 1",
        (tanggal,),
    ).fetchone()
    if row:
        return int(row["tolerance_min"])
    raw = get_setting(conn, "late_tolerance_min",
                      default=str(DEFAULT_LATE_TOLERANCE_MIN))
    try:
        return int(raw)
    except (TypeError, ValueError):
        return DEFAULT_LATE_TOLERANCE_MIN


def current_tolerance(conn: sqlite3.Connection) -> int:
    return tolerance_for(conn, datetime.now(UTC).date().isoformat())


def add_period(conn: sqlite3.Connection, *, effective_from: str,
               tolerance_min: int) -> None:
    now = datetime.now(UTC).isoformat(timespec="seconds")
    conn.execute(
        "INSERT INTO tolerance_periods "
        "(effective_from, tolerance_min, created_at) VALUES (?,?,?) "
        "ON CONFLICT(effective_from) DO UPDATE SET "
        "tolerance_min = excluded.tolerance_min",
        (effective_from, int(tolerance_min), now),
    )
    _mirror_latest(conn)


def _mirror_latest(conn: sqlite3.Connection) -> None:
    latest = conn.execute(
        "SELECT tolerance_min FROM tolerance_periods "
        "ORDER BY effective_from DESC LIMIT 1"
    ).fetchone()
    if latest:
        set_setting(conn, "late_tolerance_min", str(latest["tolerance_min"]))
