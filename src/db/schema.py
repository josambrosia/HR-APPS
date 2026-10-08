import sqlite3
from datetime import UTC, datetime
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
    manual_edited_at TEXT,
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

-- v24.0.1: pegawai yang disembunyikan dari layar Rekap Dinas Paparan saja.
-- Sengaja TERPISAH dari outlier_exclusions: yang itu berbasis periode dan
-- dipakai Dashboard/Heatmap, sedangkan ini permanen dan khusus satu layar.
CREATE TABLE IF NOT EXISTS dinas_recap_exclusions (
    employee_id INTEGER PRIMARY KEY REFERENCES employees(id) ON DELETE CASCADE,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS wa_contacts (
    employee_id  INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    year_month   TEXT    NOT NULL,
    contacted_at TEXT    NOT NULL,
    PRIMARY KEY (employee_id, year_month)
);

-- v26: jadwal kerja berlaku per tanggal (cutoff jam kantor 14 Sep 2026).
-- effective_from '1970-01-01' = sentinel "sejak awal".
CREATE TABLE IF NOT EXISTS schedule_periods (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    effective_from TEXT NOT NULL UNIQUE,
    start_time     TEXT NOT NULL,
    end_time       TEXT NOT NULL,
    created_at     TEXT NOT NULL
);

-- v26: riwayat toleransi keterlambatan (berlaku per tanggal) supaya
-- perubahan tidak mengubah warna/status bulan-bulan lama.
CREATE TABLE IF NOT EXISTS tolerance_periods (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    effective_from TEXT NOT NULL UNIQUE,
    tolerance_min  INTEGER NOT NULL,
    created_at     TEXT NOT NULL
);

-- v26: keputusan verifikasi lembur. Baris Open = ketiadaan baris di sini.
CREATE TABLE IF NOT EXISTS overtime_decisions (
    employee_id   INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    tanggal       TEXT    NOT NULL,
    status        TEXT    NOT NULL,
    approved_minutes INTEGER,
    detected_minutes_at_decision INTEGER,
    note          TEXT,
    submitted_at  TEXT,
    decided_at    TEXT,
    updated_at    TEXT NOT NULL,
    PRIMARY KEY (employee_id, tanggal)
);

CREATE INDEX IF NOT EXISTS idx_overtime_tanggal ON overtime_decisions(tanggal);
"""

DEFAULT_SETTINGS = {
    "schedule_start": "09.00",
    "schedule_end": "17.00",
    "overtime_threshold": "18.00",
    "coaching_threshold_per_day": "15",
    "severe_lateness_threshold_min": "60",
    "late_tolerance_min": "12",
}


def _migrate(conn: sqlite3.Connection) -> None:
    """Idempotent column additions and settings-key migrations for pre-existing databases.

    CREATE TABLE IF NOT EXISTS only creates missing tables — it does NOT
    add columns to a table that already exists. For an existing data/hr.db
    the export_history.kind column must be added via ALTER TABLE.

    Also migrates coaching_threshold_min (weekly, default 75) to
    coaching_threshold_per_day (daily, ≈15) by integer divide-by-5.
    """
    cols = {row[1] for row in conn.execute("PRAGMA table_info(export_history)")}
    if "kind" not in cols:
        conn.execute(
            "ALTER TABLE export_history "
            "ADD COLUMN kind TEXT NOT NULL DEFAULT 'fill'"
        )

    # v23: manual_edited_at marks rows the user corrected by hand (feeds import
    # conflict detection). CREATE TABLE IF NOT EXISTS never adds a column to an
    # existing table, so an ALTER is required for pre-existing databases.
    acols = {row[1] for row in conn.execute("PRAGMA table_info(attendance_records)")}
    if "manual_edited_at" not in acols:
        conn.execute("ALTER TABLE attendance_records ADD COLUMN manual_edited_at TEXT")

    # Coaching threshold: weekly → daily (idempotent — only writes if new key absent).
    row = conn.execute(
        "SELECT 1 FROM settings WHERE key = 'coaching_threshold_per_day'"
    ).fetchone()
    if row is None:
        old_row = conn.execute(
            "SELECT value FROM settings WHERE key = 'coaching_threshold_min'"
        ).fetchone()
        new_val = 15
        if old_row is not None:
            try:
                old = int(old_row[0])
                new_val = max(1, round(old / 5))
            except (TypeError, ValueError):
                new_val = 15
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?)",
            ("coaching_threshold_per_day", str(new_val)),
        )

    # v15: split legacy 'lupa_absen' into lupa_absen_datang / lupa_absen_pulang.
    # Idempotent: after the catch-all sweep, no rows have 'lupa_absen' left;
    # subsequent passes find nothing to update.
    #
    # Order matters:
    #   1. Rows where karyawan forgot to scan IN (masuk NULL) → datang.
    #   2. Rows where karyawan forgot to scan OUT (masuk set, keluar NULL) → pulang.
    #   3. Catch-all sweep → datang (conservative; applies penalty).
    conn.execute(
        "UPDATE attendance_records "
        "SET reason_category = 'lupa_absen_datang' "
        "WHERE reason_category = 'lupa_absen' "
        "  AND masuk IS NULL"
    )
    conn.execute(
        "UPDATE attendance_records "
        "SET reason_category = 'lupa_absen_pulang' "
        "WHERE reason_category = 'lupa_absen' "
        "  AND masuk IS NOT NULL "
        "  AND keluar IS NULL"
    )
    conn.execute(
        "UPDATE attendance_records "
        "SET reason_category = 'lupa_absen_datang' "
        "WHERE reason_category = 'lupa_absen'"
    )

    # v26: seed riwayat jadwal dari setelan tunggal. Fresh DB (belum ada
    # settings) memakai default baru; DB lama dengan default 08.00/16.00
    # dipecah pada cutoff 14 Sep 2026; nilai custom dipertahankan apa adanya.
    # Idempoten: hanya berjalan saat tabel riwayat masih kosong.
    has_period = conn.execute(
        "SELECT 1 FROM schedule_periods LIMIT 1").fetchone()
    if has_period is None:
        from src.config import (
            DEFAULT_SCHEDULE_START, DEFAULT_SCHEDULE_END,
            OLD_SCHEDULE_START, OLD_SCHEDULE_END, SCHEDULE_CUTOVER_DATE)
        srow = conn.execute(
            "SELECT value FROM settings WHERE key='schedule_start'").fetchone()
        erow = conn.execute(
            "SELECT value FROM settings WHERE key='schedule_end'").fetchone()
        start = srow[0] if srow else DEFAULT_SCHEDULE_START
        end = erow[0] if erow else DEFAULT_SCHEDULE_END
        now = datetime.now(UTC).isoformat(timespec="seconds")
        if (start, end) == (OLD_SCHEDULE_START, OLD_SCHEDULE_END):
            conn.executemany(
                "INSERT INTO schedule_periods "
                "(effective_from, start_time, end_time, created_at) "
                "VALUES (?,?,?,?)",
                [("1970-01-01", OLD_SCHEDULE_START, OLD_SCHEDULE_END, now),
                 (SCHEDULE_CUTOVER_DATE, DEFAULT_SCHEDULE_START,
                  DEFAULT_SCHEDULE_END, now)])
        else:
            conn.execute(
                "INSERT INTO schedule_periods "
                "(effective_from, start_time, end_time, created_at) "
                "VALUES (?,?,?,?)",
                ("1970-01-01", start, end, now))

    # v26: seed riwayat toleransi dari setelan tunggal. Nilai lama
    # dipertahankan sebagai periode "sejak awal"; perubahan berikutnya
    # ditambahkan ber-tanggal lewat Settings.
    has_tol = conn.execute(
        "SELECT 1 FROM tolerance_periods LIMIT 1").fetchone()
    if has_tol is None:
        from src.config import DEFAULT_LATE_TOLERANCE_MIN
        trow = conn.execute(
            "SELECT value FROM settings WHERE key='late_tolerance_min'"
        ).fetchone()
        try:
            tol = int(trow[0]) if trow else DEFAULT_LATE_TOLERANCE_MIN
        except (TypeError, ValueError):
            tol = DEFAULT_LATE_TOLERANCE_MIN
        conn.execute(
            "INSERT INTO tolerance_periods "
            "(effective_from, tolerance_min, created_at) VALUES (?,?,?)",
            ("1970-01-01", tol,
             datetime.now(UTC).isoformat(timespec="seconds")))


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
