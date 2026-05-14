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


def _active_rows(conn, employee_id):
    return conn.execute(
        "SELECT effective_from, effective_until FROM outlier_exclusions "
        "WHERE employee_id = ? ORDER BY id",
        (employee_id,),
    ).fetchall()


def test_exclude_employee_creates_active_row(temp_db_path):
    from src.db.outlier import exclude_employee, excluded_employee_ids
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = _emp(conn, "1", "A")
        exclude_employee(conn, a, "2026-04")
        rows = _active_rows(conn, a)
        assert len(rows) == 1
        assert rows[0]["effective_from"] == "2026-04"
        assert rows[0]["effective_until"] is None
        assert excluded_employee_ids(conn, "2026-04") == {a}


def test_exclude_employee_noop_if_already_active(temp_db_path):
    """Excluding someone who already has an active row does nothing."""
    from src.db.outlier import exclude_employee
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = _emp(conn, "1", "A")
        exclude_employee(conn, a, "2026-04")
        exclude_employee(conn, a, "2026-05")  # already active — no-op
        assert len(_active_rows(conn, a)) == 1


def test_revert_employee_same_month_deletes_row(temp_db_path):
    """Revert in the same month as exclude removes the row entirely."""
    from src.db.outlier import exclude_employee, revert_employee
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = _emp(conn, "1", "A")
        exclude_employee(conn, a, "2026-04")
        revert_employee(conn, a, "2026-04")
        assert _active_rows(conn, a) == []


def test_revert_employee_past_month_sets_effective_until(temp_db_path):
    """Revert in a later month closes the range at the active month."""
    from src.db.outlier import (
        exclude_employee, revert_employee, excluded_employee_ids,
    )
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = _emp(conn, "1", "A")
        exclude_employee(conn, a, "2026-04")
        revert_employee(conn, a, "2026-06")
        rows = _active_rows(conn, a)
        assert len(rows) == 1
        assert rows[0]["effective_from"] == "2026-04"
        assert rows[0]["effective_until"] == "2026-06"
        # April + May stay excluded, June onward counted again
        assert excluded_employee_ids(conn, "2026-05") == {a}
        assert excluded_employee_ids(conn, "2026-06") == set()


def test_revert_employee_noop_if_not_excluded(temp_db_path):
    from src.db.outlier import revert_employee
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = _emp(conn, "1", "A")
        revert_employee(conn, a, "2026-04")  # nothing to revert — no error
        assert _active_rows(conn, a) == []


def test_re_exclude_after_revert_creates_new_row(temp_db_path):
    from src.db.outlier import exclude_employee, revert_employee
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = _emp(conn, "1", "A")
        exclude_employee(conn, a, "2026-04")
        revert_employee(conn, a, "2026-06")
        exclude_employee(conn, a, "2026-08")
        rows = _active_rows(conn, a)
        assert len(rows) == 2
        assert rows[1]["effective_from"] == "2026-08"
        assert rows[1]["effective_until"] is None


def _att(conn, emp_id, tanggal):
    from src.db.attendance import upsert_attendance
    upsert_attendance(
        conn, employee_id=emp_id, tanggal=tanggal, hari="Senin",
        tipe="Hari Kerja", jadwal="08.00 - 16.00",
        masuk="08.05", keluar="16.00", kerja_jam=8.0,
        lembur_jam=None, terlambat_menit=5, has_issue=0,
        imported_from="W1.xls",
    )


def test_revert_all_closes_every_active_row(temp_db_path):
    from src.db.outlier import exclude_employee, revert_all, excluded_employee_ids
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = _emp(conn, "1", "A")
        b = _emp(conn, "2", "B")
        exclude_employee(conn, a, "2026-04")
        exclude_employee(conn, b, "2026-04")
        count = revert_all(conn, "2026-06")
        assert count == 2
        assert excluded_employee_ids(conn, "2026-06") == set()


def test_revert_all_returns_zero_when_nothing_active(temp_db_path):
    from src.db.outlier import revert_all
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        assert revert_all(conn, "2026-04") == 0


def test_list_active_exclusions_returns_employee_detail(temp_db_path):
    from src.db.outlier import exclude_employee, list_active_exclusions
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = _emp(conn, "1", "ALICE")
        _emp(conn, "2", "BOB")  # not excluded
        exclude_employee(conn, a, "2026-04")
        rows = list_active_exclusions(conn)
        assert len(rows) == 1
        assert rows[0]["employee_id"] == a
        assert rows[0]["nama"] == "ALICE"
        assert rows[0]["effective_from"] == "2026-04"


def test_month_roster_lists_employees_with_attendance_in_month(temp_db_path):
    from src.db.outlier import month_roster
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = _emp(conn, "1", "ALICE")
        b = _emp(conn, "2", "BOB")
        _emp(conn, "3", "CAROL")  # no attendance — should not appear
        _att(conn, a, "2026-04-01")
        _att(conn, b, "2026-04-02")
        _att(conn, a, "2026-05-01")  # also in May
        roster = month_roster(conn, "2026-04")
        names = [r["nama"] for r in roster]
        assert names == ["ALICE", "BOB"]  # sorted by nama, CAROL absent
        may = month_roster(conn, "2026-05")
        assert [r["nama"] for r in may] == ["ALICE"]
