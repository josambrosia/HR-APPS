"""Tests for list_months_with_stats — used by Riwayat Bulan screen."""
import sqlite3

from src.db.schema import DDL
from src.db.employees import upsert_employee
from src.db.attendance import upsert_attendance, set_reason, list_months_with_stats


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(DDL)
    return conn


def _add_employee(conn, no_staff="E001", nama="ANDIKA", dept="ARGA DIRGA"):
    return upsert_employee(conn, no_staff=no_staff, nama=nama, dept=dept, phone=None)


def _add_attendance(conn, employee_id, tanggal, has_issue=0):
    upsert_attendance(
        conn, employee_id=employee_id, tanggal=tanggal,
        hari=None, tipe="Hari Kerja", jadwal="08.00 - 16.00",
        masuk=None if has_issue else "08:00",
        keluar=None if has_issue else "16:00",
        kerja_jam=None if has_issue else 8.0,
        lembur_jam=0.0, terlambat_menit=0,
        has_issue=has_issue, imported_from="test.xls",
    )


def test_empty_db_returns_empty_list():
    conn = _conn()
    result = list_months_with_stats(conn)
    assert list(result) == []


def test_single_month_returns_one_entry():
    conn = _conn()
    emp_id = _add_employee(conn)
    _add_attendance(conn, emp_id, "2026-04-01")
    _add_attendance(conn, emp_id, "2026-04-02")
    rows = [dict(r) for r in list_months_with_stats(conn)]
    assert len(rows) == 1
    assert rows[0]["year_month"] == "2026-04"
    assert rows[0]["hari_count"] == 2
    assert rows[0]["records_count"] == 2
    assert rows[0]["open_issues_count"] == 0


def test_multiple_months_ordered_newest_first():
    conn = _conn()
    emp_id = _add_employee(conn)
    _add_attendance(conn, emp_id, "2026-03-15")
    _add_attendance(conn, emp_id, "2026-04-01")
    _add_attendance(conn, emp_id, "2026-05-20")
    rows = [dict(r) for r in list_months_with_stats(conn)]
    assert [r["year_month"] for r in rows] == ["2026-05", "2026-04", "2026-03"]


def test_open_issues_count_excludes_resolved():
    conn = _conn()
    emp_id = _add_employee(conn)
    _add_attendance(conn, emp_id, "2026-04-01", has_issue=1)   # open
    _add_attendance(conn, emp_id, "2026-04-02", has_issue=1)   # will resolve
    _add_attendance(conn, emp_id, "2026-04-03", has_issue=0)
    # Resolve the second one
    row_id = conn.execute(
        "SELECT id FROM attendance_records WHERE tanggal='2026-04-02'"
    ).fetchone()["id"]
    set_reason(conn, attendance_id=row_id, category="izin_sakit", detail=None)

    rows = [dict(r) for r in list_months_with_stats(conn)]
    assert len(rows) == 1
    assert rows[0]["records_count"] == 3
    assert rows[0]["open_issues_count"] == 1  # only the unresolved one
