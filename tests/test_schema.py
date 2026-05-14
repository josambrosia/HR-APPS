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
    assert rows["coaching_threshold_min"] == "75"


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
