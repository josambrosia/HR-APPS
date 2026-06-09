from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.settings import set_setting, read_late_tolerance

def test_reads_int(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        set_setting(conn, "late_tolerance_min", "20")
        assert read_late_tolerance(conn) == 20

def test_fallback(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        set_setting(conn, "late_tolerance_min", "bad")
        assert read_late_tolerance(conn) == 12
