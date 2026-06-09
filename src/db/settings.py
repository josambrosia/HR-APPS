import sqlite3
from typing import Optional

from src.config import DEFAULT_LUPA_PENALTY_MIN
from src.config import DEFAULT_SEVERE_LATENESS_THRESHOLD_MIN
from src.config import DEFAULT_LATE_TOLERANCE_MIN


def get_setting(
    conn: sqlite3.Connection, key: str, default: Optional[str] = None
) -> Optional[str]:
    row = conn.execute(
        "SELECT value FROM settings WHERE key = ?", (key,)
    ).fetchone()
    return row["value"] if row else default


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        """
        INSERT INTO settings (key, value) VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (key, value),
    )


def read_lupa_penalty_min(conn: sqlite3.Connection) -> int:
    """Read the configurable 'forgot to clock in' lateness penalty (minutes).

    Stored under the 'lupa_absen_datang_penalty_min' settings key as a string.
    Falls back to DEFAULT_LUPA_PENALTY_MIN on a missing or non-integer value.
    """
    raw = get_setting(conn, "lupa_absen_datang_penalty_min",
                      default=str(DEFAULT_LUPA_PENALTY_MIN))
    try:
        return int(raw)
    except (ValueError, TypeError):
        return DEFAULT_LUPA_PENALTY_MIN


def read_severe_lateness_threshold(conn) -> int:
    """Read severe_lateness_threshold_min as int; fall back to the default on
    missing or non-integer values."""
    raw = get_setting(conn, "severe_lateness_threshold_min",
                      default=str(DEFAULT_SEVERE_LATENESS_THRESHOLD_MIN))
    try:
        return int(raw)
    except (TypeError, ValueError):
        return DEFAULT_SEVERE_LATENESS_THRESHOLD_MIN


def read_late_tolerance(conn) -> int:
    raw = get_setting(conn, "late_tolerance_min",
                      default=str(DEFAULT_LATE_TOLERANCE_MIN))
    try:
        return int(raw)
    except (TypeError, ValueError):
        return DEFAULT_LATE_TOLERANCE_MIN
