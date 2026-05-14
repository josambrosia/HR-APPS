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

CREATE TABLE IF NOT EXISTS export_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    out_path    TEXT NOT NULL,
    template    TEXT NOT NULL,
    year_month  TEXT NOT NULL,
    filled      INTEGER NOT NULL,
    na          INTEGER NOT NULL,
    not_found   INTEGER NOT NULL,
    kind        TEXT NOT NULL DEFAULT 'fill',
    created_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_export_history_created_at
    ON export_history(created_at DESC);

CREATE TABLE IF NOT EXISTS outlier_exclusions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id     INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    effective_from  TEXT    NOT NULL,
    effective_until TEXT,
    created_at      TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_outlier_employee
    ON outlier_exclusions(employee_id);

CREATE TABLE IF NOT EXISTS holidays (
    tanggal    TEXT NOT NULL PRIMARY KEY,
    created_at TEXT NOT NULL
);
"""

DEFAULT_SETTINGS = {
    "schedule_start": "08.00",
    "schedule_end": "16.00",
    "coaching_threshold_min": "75",
}


def _migrate(conn: sqlite3.Connection) -> None:
    """Idempotent column additions for pre-existing databases.

    CREATE TABLE IF NOT EXISTS only creates missing tables — it does NOT
    add columns to a table that already exists. For an existing data/hr.db
    the export_history.kind column must be added via ALTER TABLE.
    """
    cols = {row[1] for row in conn.execute("PRAGMA table_info(export_history)")}
    if "kind" not in cols:
        conn.execute(
            "ALTER TABLE export_history "
            "ADD COLUMN kind TEXT NOT NULL DEFAULT 'fill'"
        )


def init_db(db_path: Path) -> None:
    """Create schema if missing and seed default settings (idempotent)."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(DDL)
        _migrate(conn)
        for key, value in DEFAULT_SETTINGS.items():
            conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO NOTHING",
                (key, value),
            )
        conn.commit()
    finally:
        conn.close()
