from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.settings import get_setting

def test_late_tolerance_seeded(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        assert get_setting(conn, "late_tolerance_min") == "12"
