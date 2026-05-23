import sqlite3
from src.db.schema import init_db


def test_init_db_creates_tables(temp_db_path):
    init_db(temp_db_path)
    with sqlite3.connect(temp_db_path) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
    names = [r[0] for r in rows]
    assert "employees" in names
    assert "attendance_records" in names
    assert "settings" in names


def test_init_db_seeds_default_settings(temp_db_path):
    init_db(temp_db_path)
    with sqlite3.connect(temp_db_path) as conn:
        rows = dict(conn.execute("SELECT key, value FROM settings").fetchall())
    assert rows["schedule_start"] == "08.00"
    assert rows["schedule_end"] == "16.00"
    assert rows["coaching_threshold_per_day"] == "15"


def test_init_db_idempotent(temp_db_path):
    init_db(temp_db_path)
    init_db(temp_db_path)  # second call must not raise
    with sqlite3.connect(temp_db_path) as conn:
        cnt = conn.execute("SELECT COUNT(*) FROM settings").fetchone()[0]
    assert cnt == 3  # not duplicated


def test_outlier_exclusions_table_created(temp_db_path):
    """init_db creates the outlier_exclusions table."""
    from src.db.schema import init_db
    from src.db.connection import get_connection
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        row = conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='outlier_exclusions'"
        ).fetchone()
    assert row is not None


def test_holidays_table_created(temp_db_path):
    """init_db creates the holidays table with correct columns and constraints."""
    init_db(temp_db_path)
    with sqlite3.connect(temp_db_path) as conn:
        row = conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='holidays'"
        ).fetchone()
    assert row is not None

    with sqlite3.connect(temp_db_path) as conn:
        info = {r[1]: r for r in conn.execute("PRAGMA table_info(holidays)")}
    assert "tanggal" in info and "created_at" in info
    assert info["tanggal"][5] == 1      # pk flag
    assert info["tanggal"][3] == 1      # notnull flag
    assert info["created_at"][3] == 1   # notnull flag


def test_export_history_has_kind_column(temp_db_path):
    """export_history has the kind column after init_db (new DB)."""
    init_db(temp_db_path)
    with sqlite3.connect(temp_db_path) as conn:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(export_history)")}
    assert "kind" in cols


def test_migrate_adds_kind_to_legacy_export_history(temp_db_path):
    """A pre-existing export_history WITHOUT kind gets the column added and back-filled."""
    with sqlite3.connect(temp_db_path) as conn:
        conn.execute(
            """
            CREATE TABLE export_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                out_path TEXT NOT NULL, template TEXT NOT NULL,
                year_month TEXT NOT NULL, filled INTEGER NOT NULL,
                na INTEGER NOT NULL, not_found INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "INSERT INTO export_history "
            "(out_path, template, year_month, filled, na, not_found, created_at) "
            "VALUES ('p', 't', '2024-01', 1, 0, 0, '2024-01-01T00:00:00+00:00')"
        )
        conn.commit()
    init_db(temp_db_path)  # must migrate in place without error
    with sqlite3.connect(temp_db_path) as conn:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(export_history)")}
        kind_val = conn.execute("SELECT kind FROM export_history").fetchone()[0]
    assert "kind" in cols
    assert kind_val == "fill"


def test_migrate_seeds_threshold_per_day_on_fresh_db(temp_db_path):
    """A brand-new DB has no old key; migration seeds coaching_threshold_per_day = 15."""
    init_db(temp_db_path)
    with sqlite3.connect(temp_db_path) as conn:
        row = conn.execute(
            "SELECT value FROM settings WHERE key = 'coaching_threshold_per_day'"
        ).fetchone()
    assert row is not None
    assert row[0] == "15"


def test_migrate_converts_existing_weekly_threshold(temp_db_path):
    """Existing coaching_threshold_min='60' migrates to coaching_threshold_per_day='12'."""
    with sqlite3.connect(temp_db_path) as conn:
        conn.executescript(
            "CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT);"
        )
        conn.execute(
            "INSERT INTO settings (key, value) VALUES ('coaching_threshold_min', '60')"
        )
        conn.commit()
    init_db(temp_db_path)
    with sqlite3.connect(temp_db_path) as conn:
        per_day = conn.execute(
            "SELECT value FROM settings WHERE key = 'coaching_threshold_per_day'"
        ).fetchone()
        old = conn.execute(
            "SELECT value FROM settings WHERE key = 'coaching_threshold_min'"
        ).fetchone()
    assert per_day[0] == "12"
    assert old[0] == "60"  # orphan preserved, not deleted


def test_migrate_converts_default_75_to_15(temp_db_path):
    """Existing coaching_threshold_min='75' (old default) migrates to '15'."""
    with sqlite3.connect(temp_db_path) as conn:
        conn.executescript(
            "CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT);"
        )
        conn.execute(
            "INSERT INTO settings (key, value) VALUES ('coaching_threshold_min', '75')"
        )
        conn.commit()
    init_db(temp_db_path)
    with sqlite3.connect(temp_db_path) as conn:
        per_day = conn.execute(
            "SELECT value FROM settings WHERE key = 'coaching_threshold_per_day'"
        ).fetchone()
    assert per_day[0] == "15"


def test_migrate_threshold_idempotent(temp_db_path):
    """Second init_db call leaves coaching_threshold_per_day untouched."""
    init_db(temp_db_path)
    # Simulate user changing the value
    with sqlite3.connect(temp_db_path) as conn:
        conn.execute(
            "UPDATE settings SET value = '20' WHERE key = 'coaching_threshold_per_day'"
        )
        conn.commit()
    init_db(temp_db_path)
    with sqlite3.connect(temp_db_path) as conn:
        per_day = conn.execute(
            "SELECT value FROM settings WHERE key = 'coaching_threshold_per_day'"
        ).fetchone()
    assert per_day[0] == "20"


def test_migrate_splits_legacy_lupa_absen_datang(temp_db_path):
    """Legacy lupa_absen rows with masuk=NULL migrate to lupa_absen_datang."""
    init_db(temp_db_path)
    with sqlite3.connect(temp_db_path) as conn:
        # Set up an employee + an attendance row with legacy lupa_absen + masuk=NULL
        conn.execute(
            "INSERT INTO employees (no_staff, nama) VALUES ('1', 'ANDI')"
        )
        emp_id = conn.execute("SELECT id FROM employees WHERE no_staff='1'").fetchone()[0]
        conn.execute(
            "INSERT INTO attendance_records "
            "(employee_id, tanggal, hari, tipe, masuk, keluar, "
            "has_issue, reason_category, imported_from, imported_at) "
            "VALUES (?, '2026-04-01', 'Rabu', 'Hari Kerja', NULL, '16:00', "
            "1, 'lupa_absen', 't.xls', '2026-04-01T00:00:00+00:00')",
            (emp_id,),
        )
        conn.commit()
    # Re-run init_db to trigger migration
    init_db(temp_db_path)
    with sqlite3.connect(temp_db_path) as conn:
        cat = conn.execute(
            "SELECT reason_category FROM attendance_records"
        ).fetchone()[0]
    assert cat == "lupa_absen_datang"


def test_migrate_splits_legacy_lupa_absen_pulang(temp_db_path):
    """Legacy lupa_absen rows with masuk set, keluar=NULL migrate to lupa_absen_pulang."""
    init_db(temp_db_path)
    with sqlite3.connect(temp_db_path) as conn:
        conn.execute(
            "INSERT INTO employees (no_staff, nama) VALUES ('1', 'ANDI')"
        )
        emp_id = conn.execute("SELECT id FROM employees WHERE no_staff='1'").fetchone()[0]
        conn.execute(
            "INSERT INTO attendance_records "
            "(employee_id, tanggal, hari, tipe, masuk, keluar, "
            "has_issue, reason_category, imported_from, imported_at) "
            "VALUES (?, '2026-04-01', 'Rabu', 'Hari Kerja', '08:05', NULL, "
            "1, 'lupa_absen', 't.xls', '2026-04-01T00:00:00+00:00')",
            (emp_id,),
        )
        conn.commit()
    init_db(temp_db_path)
    with sqlite3.connect(temp_db_path) as conn:
        cat = conn.execute(
            "SELECT reason_category FROM attendance_records"
        ).fetchone()[0]
    assert cat == "lupa_absen_pulang"


def test_migrate_splits_legacy_lupa_absen_fallback_both_null(temp_db_path):
    """Legacy lupa_absen rows with both masuk AND keluar NULL fallback to
    lupa_absen_datang (conservative — applies penalty)."""
    init_db(temp_db_path)
    with sqlite3.connect(temp_db_path) as conn:
        conn.execute(
            "INSERT INTO employees (no_staff, nama) VALUES ('1', 'ANDI')"
        )
        emp_id = conn.execute("SELECT id FROM employees WHERE no_staff='1'").fetchone()[0]
        conn.execute(
            "INSERT INTO attendance_records "
            "(employee_id, tanggal, hari, tipe, masuk, keluar, "
            "has_issue, reason_category, imported_from, imported_at) "
            "VALUES (?, '2026-04-01', 'Rabu', 'Hari Kerja', NULL, NULL, "
            "1, 'lupa_absen', 't.xls', '2026-04-01T00:00:00+00:00')",
            (emp_id,),
        )
        conn.commit()
    init_db(temp_db_path)
    with sqlite3.connect(temp_db_path) as conn:
        cat = conn.execute(
            "SELECT reason_category FROM attendance_records"
        ).fetchone()[0]
    assert cat == "lupa_absen_datang"


def test_migrate_lupa_absen_idempotent(temp_db_path):
    """Running migration twice leaves the table in the same state — no
    rows are still 'lupa_absen', and split rows aren't re-touched."""
    init_db(temp_db_path)
    with sqlite3.connect(temp_db_path) as conn:
        conn.execute(
            "INSERT INTO employees (no_staff, nama) VALUES ('1', 'ANDI')"
        )
        emp_id = conn.execute("SELECT id FROM employees WHERE no_staff='1'").fetchone()[0]
        conn.execute(
            "INSERT INTO attendance_records "
            "(employee_id, tanggal, hari, tipe, masuk, keluar, "
            "has_issue, reason_category, imported_from, imported_at) "
            "VALUES (?, '2026-04-01', 'Rabu', 'Hari Kerja', NULL, '16:00', "
            "1, 'lupa_absen', 't.xls', '2026-04-01T00:00:00+00:00')",
            (emp_id,),
        )
        conn.commit()
    init_db(temp_db_path)
    init_db(temp_db_path)  # second migration pass
    with sqlite3.connect(temp_db_path) as conn:
        cat = conn.execute(
            "SELECT reason_category FROM attendance_records"
        ).fetchone()[0]
        legacy_count = conn.execute(
            "SELECT COUNT(*) FROM attendance_records WHERE reason_category='lupa_absen'"
        ).fetchone()[0]
    assert cat == "lupa_absen_datang"
    assert legacy_count == 0
