# tests/test_settings_read_severe_lateness.py
from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.settings import set_setting, read_severe_lateness_threshold


def test_reads_int_value(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        set_setting(conn, "severe_lateness_threshold_min", "90")
        assert read_severe_lateness_threshold(conn) == 90


def test_fallback_on_invalid(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        set_setting(conn, "severe_lateness_threshold_min", "not-a-number")
        assert read_severe_lateness_threshold(conn) == 60


def test_fallback_on_missing(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        conn.execute("DELETE FROM settings WHERE key='severe_lateness_threshold_min'")
        assert read_severe_lateness_threshold(conn) == 60
