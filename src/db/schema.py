import sqlite3
from pathlib import Path

DDL = """
CREATE TABLE IF NOT EXISTS employees (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    no_staff  TEXT    UNIQUE NOT NULL,
    nama      TEXT    NOT NULL,
    dept      TEXT,
    phone     TEXT,
    active    INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS attendance_records (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id     INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    tanggal         TEXT    NOT NULL,
    hari            TEXT,
    tipe            TEXT,
    jadwal          TEXT,
    masuk           TEXT,
    keluar          TEXT,
    kerja_jam       REAL,
    lembur_jam      REAL,
    terlambat_menit INTEGER,
    has_issue       INTEGER NOT NULL DEFAULT 0,
    reason_category TEXT,
    reason_detail   TEXT,
    resolved_at     TEXT,
    imported_from   TEXT,
    imported_at     TEXT,
    UNIQUE (employee_id, tanggal)
);

CREATE INDEX IF NOT EXISTS idx_attendance_tanggal ON attendance_records(tanggal);
CREATE INDEX IF NOT EXISTS idx_attendance_has_issue ON attendance_records(has_issue);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS coaching_sessions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    week_start  TEXT    NOT NULL,
    coached_at  TEXT    NOT NULL,
    notes       TEXT,
    UNIQUE (employee_id, week_start)
);

CREATE INDEX IF NOT EXISTS idx_coaching_week ON coaching_sessions(week_start);
"""

DEFAULT_SETTINGS = {
    "schedule_start": "08.00",
    "schedule_end": "16.00",
    "coaching_threshold_min": "75",
}


def init_db(db_path: Path) -> None:
    """Create schema if missing and seed default settings (idempotent)."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(DDL)
        for key, value in DEFAULT_SETTINGS.items():
            conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO NOTHING",
                (key, value),
            )
        conn.commit()
    finally:
        conn.close()
