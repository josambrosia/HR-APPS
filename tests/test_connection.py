import sqlite3
from src.db.schema import init_db
from src.db.connection import get_connection


def test_get_connection_enables_foreign_keys(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        result = conn.execute("PRAGMA foreign_keys").fetchone()
        assert result[0] == 1


def test_get_connection_returns_dict_rows(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        row = conn.execute("SELECT 'abc' AS letters, 7 AS num").fetchone()
        assert row["letters"] == "abc"
        assert row["num"] == 7


def test_context_manager_closes_connection(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        pass
    # After exit, conn is closed → query should raise
    import pytest
    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")
