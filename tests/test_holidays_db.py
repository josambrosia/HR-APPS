"""Tests for src/db/holidays.py — Hari Libur data access."""
from datetime import datetime, UTC

from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.attendance import upsert_attendance


def _emp(conn, no, nama):
    return upsert_employee(conn, no_staff=no, nama=nama, dept="X")


def _att(conn, emp_id, tanggal, *, tipe="Hari Kerja", masuk="08.05",
         keluar="16.00", has_issue=0, reason_category=None):
    upsert_attendance(
        conn, employee_id=emp_id, tanggal=tanggal, hari="Senin",
        tipe=tipe, jadwal="08.00 - 16.00",
        masuk=masuk, keluar=keluar, kerja_jam=8.0,
        lembur_jam=None, terlambat_menit=5, has_issue=has_issue,
        imported_from="W1.xls",
    )
    if reason_category is not None:
        conn.execute(
            "UPDATE attendance_records SET reason_category=? "
            "WHERE employee_id=? AND tanggal=?",
            (reason_category, emp_id, tanggal),
        )


def _mark_direct(conn, tanggal):
    """Seed a holidays row directly (no stamping) for read-query tests."""
    conn.execute(
        "INSERT OR IGNORE INTO holidays (tanggal, created_at) VALUES (?, ?)",
        (tanggal, datetime.now(UTC).isoformat(timespec="seconds")),
    )


def test_list_holidays_empty(temp_db_path):
    from src.db.holidays import list_holidays
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        assert list_holidays(conn) == []


def test_list_holidays_sorted(temp_db_path):
    from src.db.holidays import list_holidays
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        _mark_direct(conn, "2026-04-17")
        _mark_direct(conn, "2026-04-03")
        assert list_holidays(conn) == ["2026-04-03", "2026-04-17"]


def test_holiday_dates_in_month_filters_by_month(temp_db_path):
    from src.db.holidays import holiday_dates_in_month
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        _mark_direct(conn, "2026-04-03")
        _mark_direct(conn, "2026-05-01")
        assert holiday_dates_in_month(conn, "2026-04") == {"2026-04-03"}
        assert holiday_dates_in_month(conn, "2026-05") == {"2026-05-01"}


def test_workday_roster_lists_workdays_with_flags(temp_db_path):
    from src.db.holidays import workday_roster
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = _emp(conn, "1", "ANDI")
        _att(conn, a, "2026-04-01", has_issue=1)                       # open issue
        _att(conn, a, "2026-04-03", tipe="Hari Libur",
             reason_category="libur", has_issue=1)                     # already holiday
        _att(conn, a, "2026-04-05", tipe="Istirahat")                  # weekend — excluded
        _mark_direct(conn, "2026-04-03")
        roster = workday_roster(conn, "2026-04")
        assert [r["tanggal"] for r in roster] == ["2026-04-01", "2026-04-03"]
        by_date = {r["tanggal"]: r for r in roster}
        assert by_date["2026-04-01"]["is_holiday"] is False
        assert by_date["2026-04-01"]["issue_count"] == 1   # open issue
        assert by_date["2026-04-03"]["is_holiday"] is True
        assert by_date["2026-04-03"]["issue_count"] == 1   # libur-resolved
        assert by_date["2026-04-01"]["hari"] == "Senin"
