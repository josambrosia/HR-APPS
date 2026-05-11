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
