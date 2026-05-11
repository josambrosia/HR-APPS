from datetime import datetime
from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.attendance import upsert_attendance, set_reason, list_open_issues, list_all_for_period


def _seed_employee(conn):
    return upsert_employee(conn, no_staff="9001", nama="BUDI", dept="TEST")


def test_upsert_inserts_new(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        emp_id = _seed_employee(conn)
        upsert_attendance(
            conn,
            employee_id=emp_id,
            tanggal="2026-04-01",
            hari="Senin",
            tipe="Hari Kerja",
            jadwal="08.00 - 16.00",
            masuk="08.05",
            keluar="16.30",
            kerja_jam=7.9,
            lembur_jam=None,
            terlambat_menit=5,
            has_issue=0,
            imported_from="W1.xls",
        )
        row = conn.execute("SELECT * FROM attendance_records").fetchone()
        assert row["masuk"] == "08.05"
        assert row["has_issue"] == 0


def test_upsert_preserves_reason_on_reimport(temp_db_path):
    """CRITICAL: re-importing same fingerprint row must NOT clear user-entered reason."""
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        emp_id = _seed_employee(conn)
        upsert_attendance(
            conn, employee_id=emp_id, tanggal="2026-04-02",
            hari="Selasa", tipe="Hari Kerja", jadwal="08.00 - 16.00",
            masuk="08.10", keluar=None, kerja_jam=None, lembur_jam=None,
            terlambat_menit=10, has_issue=1, imported_from="W1.xls",
        )
        # User sets reason
        rec = conn.execute("SELECT id FROM attendance_records").fetchone()
        set_reason(conn, attendance_id=rec["id"], category="lupa_absen", detail=None)

        # Re-import same row (e.g., user re-pulls W1)
        upsert_attendance(
            conn, employee_id=emp_id, tanggal="2026-04-02",
            hari="Selasa", tipe="Hari Kerja", jadwal="08.00 - 16.00",
            masuk="08.10", keluar=None, kerja_jam=None, lembur_jam=None,
            terlambat_menit=10, has_issue=1, imported_from="W1.xls",
        )
        row = conn.execute("SELECT * FROM attendance_records").fetchone()
        assert row["reason_category"] == "lupa_absen"  # preserved
        assert row["resolved_at"] is not None


def test_set_reason_marks_resolved(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        emp_id = _seed_employee(conn)
        upsert_attendance(
            conn, employee_id=emp_id, tanggal="2026-04-02",
            hari="Selasa", tipe="Hari Kerja", jadwal="08.00 - 16.00",
            masuk=None, keluar=None, kerja_jam=None, lembur_jam=None,
            terlambat_menit=None, has_issue=1, imported_from="W1.xls",
        )
        rec = conn.execute("SELECT id FROM attendance_records").fetchone()
        set_reason(conn, attendance_id=rec["id"], category="cuti", detail=None)
        row = conn.execute("SELECT * FROM attendance_records").fetchone()
        assert row["reason_category"] == "cuti"
        assert row["resolved_at"] is not None


def test_list_open_issues_returns_only_unresolved(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        emp_id = _seed_employee(conn)
        # 2 issues, 1 with reason set
        upsert_attendance(conn, employee_id=emp_id, tanggal="2026-04-02",
                          hari="Selasa", tipe="Hari Kerja", jadwal="08.00 - 16.00",
                          masuk="08.10", keluar=None, kerja_jam=None, lembur_jam=None,
                          terlambat_menit=10, has_issue=1, imported_from="W1.xls")
        upsert_attendance(conn, employee_id=emp_id, tanggal="2026-04-03",
                          hari="Rabu", tipe="Hari Kerja", jadwal="08.00 - 16.00",
                          masuk=None, keluar=None, kerja_jam=None, lembur_jam=None,
                          terlambat_menit=None, has_issue=1, imported_from="W1.xls")
        first = conn.execute(
            "SELECT id FROM attendance_records WHERE tanggal='2026-04-02'"
        ).fetchone()
        set_reason(conn, attendance_id=first["id"], category="lupa_absen", detail=None)

        open_ones = list_open_issues(conn)
        assert len(open_ones) == 1
        assert open_ones[0]["tanggal"] == "2026-04-03"
