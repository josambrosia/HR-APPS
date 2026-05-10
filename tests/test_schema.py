import sqlite3
from src.db.schema import init_db
from src.config import REASON_CATEGORIES


def test_init_db_creates_tables(temp_db_path):
    init_db(temp_db_path)
    conn = sqlite3.connect(temp_db_path)
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    names = [r[0] for r in rows]
    assert "employees" in names
    assert "attendance_records" in names
    assert "settings" in names


def test_init_db_seeds_default_settings(temp_db_path):
    init_db(temp_db_path)
    conn = sqlite3.connect(temp_db_path)
    rows = dict(conn.execute("SELECT key, value FROM settings").fetchall())
    assert rows["schedule_start"] == "08.00"
    assert rows["schedule_end"] == "16.00"
    assert rows["coaching_threshold_min"] == "75"


def test_init_db_idempotent(temp_db_path):
    init_db(temp_db_path)
    init_db(temp_db_path)  # second call must not raise
    conn = sqlite3.connect(temp_db_path)
    cnt = conn.execute("SELECT COUNT(*) FROM settings").fetchone()[0]
    assert cnt == 3  # not duplicated
