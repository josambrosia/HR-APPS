"""Tests for src/db/outlier.py — Outlier exclusion data access."""
from datetime import datetime, UTC

from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.employees import upsert_employee


def _emp(conn, no, nama):
    return upsert_employee(conn, no_staff=no, nama=nama, dept="X")


def _insert_exclusion(conn, employee_id, effective_from, effective_until=None):
    """Direct insert helper for tests that need to seed exclusion rows."""
    conn.execute(
        "INSERT INTO outlier_exclusions "
        "(employee_id, effective_from, effective_until, created_at) "
        "VALUES (?, ?, ?, ?)",
        (employee_id, effective_from, effective_until,
         datetime.now(UTC).isoformat(timespec="seconds")),
    )


def test_excluded_employee_ids_empty_when_no_rows(temp_db_path):
    from src.db.outlier import excluded_employee_ids
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        assert excluded_employee_ids(conn, "2026-04") == set()


def test_excluded_employee_ids_active_ongoing(temp_db_path):
    """Row with effective_until NULL is excluded for effective_from onward."""
    from src.db.outlier import excluded_employee_ids
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = _emp(conn, "1", "A")
        _insert_exclusion(conn, a, "2026-04", None)
        assert excluded_employee_ids(conn, "2026-03") == set()    # before
        assert excluded_employee_ids(conn, "2026-04") == {a}      # at start
        assert excluded_employee_ids(conn, "2026-09") == {a}      # forward


def test_excluded_employee_ids_closed_range(temp_db_path):
    """Row with effective_until set excludes [from, until) — until is exclusive."""
    from src.db.outlier import excluded_employee_ids
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = _emp(conn, "1", "A")
        _insert_exclusion(conn, a, "2026-04", "2026-06")
        assert excluded_employee_ids(conn, "2026-03") == set()    # before from
        assert excluded_employee_ids(conn, "2026-04") == {a}      # at from
        assert excluded_employee_ids(conn, "2026-05") == {a}      # inside
        assert excluded_employee_ids(conn, "2026-06") == set()    # at until (exclusive)
        assert excluded_employee_ids(conn, "2026-07") == set()    # after


def test_exclusion_sql_empty_set_is_noop(temp_db_path):
    from src.db.outlier import exclusion_sql
    frag, params = exclusion_sql(set())
    assert frag == ""
    assert params == ()


def test_exclusion_sql_builds_not_in_clause():
    from src.db.outlier import exclusion_sql
    frag, params = exclusion_sql({3, 7})
    assert frag.strip().startswith("AND employee_id NOT IN (")
    assert frag.count("?") == 2
    assert set(params) == {3, 7}


def test_exclusion_sql_custom_column():
    from src.db.outlier import exclusion_sql
    frag, _ = exclusion_sql({1}, column="e.id")
    assert "e.id NOT IN (" in frag
