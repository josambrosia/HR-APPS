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
