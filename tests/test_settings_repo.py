from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.settings import get_setting, set_setting


def test_get_default_settings(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        assert get_setting(conn, "schedule_start") == "08.00"
        assert get_setting(conn, "coaching_threshold_min") == "75"


def test_set_setting_inserts_and_updates(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        set_setting(conn, "current_month", "2026-04")
        assert get_setting(conn, "current_month") == "2026-04"
        set_setting(conn, "current_month", "2026-05")
        assert get_setting(conn, "current_month") == "2026-05"


def test_get_missing_setting_returns_default(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        assert get_setting(conn, "no_such_key", default="x") == "x"
        assert get_setting(conn, "no_such_key") is None
