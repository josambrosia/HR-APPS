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


def _row(conn, emp_id, tanggal):
    return conn.execute(
        "SELECT tipe, reason_category, resolved_at FROM attendance_records "
        "WHERE employee_id=? AND tanggal=?", (emp_id, tanggal),
    ).fetchone()


def test_mark_holidays_stamps_tipe_and_inserts_row(temp_db_path):
    from src.db.holidays import mark_holidays, list_holidays
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = _emp(conn, "1", "ANDI")
        _att(conn, a, "2026-04-03")
        result = mark_holidays(conn, ["2026-04-03"])
        assert list_holidays(conn) == ["2026-04-03"]
        assert _row(conn, a, "2026-04-03")["tipe"] == "Hari Libur"
        assert result["dates_marked"] == 1


def test_mark_holidays_auto_resolves_only_open_issues(temp_db_path):
    from src.db.holidays import mark_holidays
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = _emp(conn, "1", "OPEN")
        b = _emp(conn, "2", "MANUAL")
        _att(conn, a, "2026-04-03", has_issue=1)                          # open
        _att(conn, b, "2026-04-03", has_issue=1, reason_category="izin_sakit")
        result = mark_holidays(conn, ["2026-04-03"])
        assert result["issues_resolved"] == 1                             # only the open one
        assert _row(conn, a, "2026-04-03")["reason_category"] == "libur"
        assert _row(conn, b, "2026-04-03")["reason_category"] == "izin_sakit"


def test_mark_holidays_idempotent(temp_db_path):
    from src.db.holidays import mark_holidays, list_holidays
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = _emp(conn, "1", "ANDI")
        _att(conn, a, "2026-04-03", has_issue=1)
        mark_holidays(conn, ["2026-04-03"])
        mark_holidays(conn, ["2026-04-03"])  # second call — no dup, no error
        assert list_holidays(conn) == ["2026-04-03"]


def test_unmark_holidays_restores_tipe_and_reopens_libur_issues(temp_db_path):
    from src.db.holidays import mark_holidays, unmark_holidays, list_holidays
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = _emp(conn, "1", "ANDI")
        _att(conn, a, "2026-04-03", has_issue=1)
        mark_holidays(conn, ["2026-04-03"])
        result = unmark_holidays(conn, ["2026-04-03"])
        assert list_holidays(conn) == []
        row = _row(conn, a, "2026-04-03")
        assert row["tipe"] == "Hari Kerja"
        assert row["reason_category"] is None
        assert result["issues_reopened"] == 1


def test_unmark_holidays_leaves_manually_resolved_issues(temp_db_path):
    from src.db.holidays import mark_holidays, unmark_holidays
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        b = _emp(conn, "2", "MANUAL")
        _att(conn, b, "2026-04-03", has_issue=1, reason_category="izin_sakit")
        mark_holidays(conn, ["2026-04-03"])
        unmark_holidays(conn, ["2026-04-03"])
        assert _row(conn, b, "2026-04-03")["reason_category"] == "izin_sakit"


def test_restamp_holidays_reapplies_after_simulated_reimport(temp_db_path):
    from src.db.holidays import mark_holidays, restamp_holidays
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = _emp(conn, "1", "ANDI")
        _att(conn, a, "2026-04-03", has_issue=1)
        mark_holidays(conn, ["2026-04-03"])
        # simulate re-import: upsert overwrites tipe back to 'Hari Kerja'
        _att(conn, a, "2026-04-03", has_issue=1)
        assert _row(conn, a, "2026-04-03")["tipe"] == "Hari Kerja"   # lost
        # a NEW employee imported later with an open issue on the holiday date
        c = _emp(conn, "2", "LATE")
        _att(conn, c, "2026-04-03", has_issue=1)
        restamp_holidays(conn)
        assert _row(conn, a, "2026-04-03")["tipe"] == "Hari Libur"   # restored
        assert _row(conn, c, "2026-04-03")["tipe"] == "Hari Libur"
        assert _row(conn, c, "2026-04-03")["reason_category"] == "libur"


def test_working_days_count_empty_range(temp_db_path):
    from src.db.holidays import working_days_count
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        assert working_days_count(conn, "2026-04-01", "2026-04-07") == 0


def test_working_days_count_only_hari_kerja(temp_db_path):
    """Counts only distinct dates with tipe='Hari Kerja'. Hari Libur and Istirahat excluded."""
    from src.db.holidays import working_days_count
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        emp = _emp(conn, "1", "ANI")
        # 3 Hari Kerja dates (one outside the range, one is Hari Libur, one Istirahat)
        _att(conn, emp, "2026-04-13", tipe="Hari Kerja")          # in range, kerja
        _att(conn, emp, "2026-04-14", tipe="Hari Kerja")          # in range, kerja
        _att(conn, emp, "2026-04-15", tipe="Hari Libur")          # in range, libur
        _att(conn, emp, "2026-04-16", tipe="Istirahat")           # in range, istirahat
        _att(conn, emp, "2026-04-17", tipe="Hari Kerja")          # in range, kerja
        _att(conn, emp, "2026-04-20", tipe="Hari Kerja")          # OUT of range
        assert working_days_count(conn, "2026-04-13", "2026-04-19") == 3


def test_working_days_count_distinct_dates(temp_db_path):
    """Multiple employees on the same date → counted once."""
    from src.db.holidays import working_days_count
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        e1 = _emp(conn, "1", "ANI")
        e2 = _emp(conn, "2", "BUDI")
        _att(conn, e1, "2026-04-13", tipe="Hari Kerja")
        _att(conn, e2, "2026-04-13", tipe="Hari Kerja")
        _att(conn, e1, "2026-04-14", tipe="Hari Kerja")
        assert working_days_count(conn, "2026-04-13", "2026-04-14") == 2


def test_working_days_count_inclusive_bounds(temp_db_path):
    """Date-range filter is BETWEEN — inclusive on both ends."""
    from src.db.holidays import working_days_count
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        emp = _emp(conn, "1", "ANI")
        _att(conn, emp, "2026-04-13", tipe="Hari Kerja")  # start boundary
        _att(conn, emp, "2026-04-17", tipe="Hari Kerja")  # end boundary
        _att(conn, emp, "2026-04-15", tipe="Hari Kerja")  # middle
        assert working_days_count(conn, "2026-04-13", "2026-04-17") == 3
