from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.attendance import upsert_attendance
from src.core.issue_summary import render_summary_for_employee


def test_summary_for_employee_with_no_issues(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        emp_id = upsert_employee(conn, no_staff="9001", nama="BUDI", dept="TEST")
        result = render_summary_for_employee(conn, emp_id)
        assert result == ""  # empty string when nothing to follow up


def test_summary_includes_hari_tanggal_and_kind(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        emp_id = upsert_employee(conn, no_staff="9001", nama="ANDIKA", dept="A")
        # lupa pulang
        upsert_attendance(conn, employee_id=emp_id, tanggal="2026-04-09",
                          hari="Kamis", tipe="Hari Kerja", jadwal="08.00 - 16.00",
                          masuk="08.14", keluar=None, kerja_jam=None,
                          lembur_jam=None, terlambat_menit=14,
                          has_issue=1, imported_from="W2.xls")
        # tidak masuk
        upsert_attendance(conn, employee_id=emp_id, tanggal="2026-04-10",
                          hari="Jumat", tipe="Hari Kerja", jadwal="08.00 - 16.00",
                          masuk=None, keluar=None, kerja_jam=None,
                          lembur_jam=None, terlambat_menit=None,
                          has_issue=1, imported_from="W2.xls")
        text = render_summary_for_employee(conn, emp_id)
        assert "ANDIKA" in text
        assert "(2 issue)" in text
        assert "Kamis, 9 April 2026" in text
        assert "lupa absen pulang" in text
        assert "Jumat, 10 April 2026" in text
        assert "tidak masuk" in text


def test_summary_excludes_resolved_issues(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        from src.db.attendance import set_reason
        emp_id = upsert_employee(conn, no_staff="9001", nama="X", dept="A")
        upsert_attendance(conn, employee_id=emp_id, tanggal="2026-04-09",
                          hari="Kamis", tipe="Hari Kerja", jadwal="08.00 - 16.00",
                          masuk=None, keluar=None, kerja_jam=None,
                          lembur_jam=None, terlambat_menit=None,
                          has_issue=1, imported_from="W2.xls")
        rec = conn.execute("SELECT id FROM attendance_records").fetchone()
        set_reason(conn, attendance_id=rec["id"], category="cuti", detail=None)
        assert render_summary_for_employee(conn, emp_id) == ""


def test_summary_filters_by_year_month(temp_db_path):
    """year_month filter scopes issues to that month only (WA Assistant use case)."""
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        emp_id = upsert_employee(conn, no_staff="9001", nama="SITI", dept="A")
        # April issue
        upsert_attendance(conn, employee_id=emp_id, tanggal="2026-04-09",
                          hari="Kamis", tipe="Hari Kerja", jadwal="08.00 - 16.00",
                          masuk=None, keluar=None, kerja_jam=None,
                          lembur_jam=None, terlambat_menit=None,
                          has_issue=1, imported_from="W2.xls")
        # May issue
        upsert_attendance(conn, employee_id=emp_id, tanggal="2026-05-04",
                          hari="Senin", tipe="Hari Kerja", jadwal="08.00 - 16.00",
                          masuk="08.05", keluar=None, kerja_jam=None,
                          lembur_jam=None, terlambat_menit=5,
                          has_issue=1, imported_from="W2.xls")

        # No filter: both issues appear.
        text_all = render_summary_for_employee(conn, emp_id)
        assert "(2 issue)" in text_all
        assert "9 April 2026" in text_all
        assert "4 Mei 2026" in text_all

        # Filter to April: only April issue.
        text_april = render_summary_for_employee(conn, emp_id, year_month="2026-04")
        assert "(1 issue)" in text_april
        assert "9 April 2026" in text_april
        assert "4 Mei 2026" not in text_april

        # Filter to May: only May issue.
        text_may = render_summary_for_employee(conn, emp_id, year_month="2026-05")
        assert "(1 issue)" in text_may
        assert "4 Mei 2026" in text_may
        assert "9 April 2026" not in text_may

        # Filter to a month with no issues: empty string.
        assert render_summary_for_employee(conn, emp_id, year_month="2026-06") == ""
