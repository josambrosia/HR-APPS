from datetime import datetime
from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.attendance import (
    upsert_attendance, set_reason, list_open_issues, list_all_for_period,
    list_employees_with_open_issues, list_open_issues_for_employee,
)


def _seed_employee(conn):
    return upsert_employee(conn, no_staff="9001", nama="BUDI", dept="TEST")


def _seed_issue(conn, emp_id, tanggal, *, masuk=None, keluar=None, has_issue=1):
    upsert_attendance(
        conn, employee_id=emp_id, tanggal=tanggal, hari="Senin",
        tipe="Hari Kerja", jadwal="08.00 - 16.00",
        masuk=masuk, keluar=keluar, kerja_jam=None, lembur_jam=None,
        terlambat_menit=None, has_issue=has_issue, imported_from="W1.xls",
    )


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
        set_reason(conn, attendance_id=rec["id"], category="lupa_absen_pulang", detail=None)

        # Re-import same row (e.g., user re-pulls W1)
        upsert_attendance(
            conn, employee_id=emp_id, tanggal="2026-04-02",
            hari="Selasa", tipe="Hari Kerja", jadwal="08.00 - 16.00",
            masuk="08.10", keluar=None, kerja_jam=None, lembur_jam=None,
            terlambat_menit=10, has_issue=1, imported_from="W1.xls",
        )
        row = conn.execute("SELECT * FROM attendance_records").fetchone()
        assert row["reason_category"] == "lupa_absen_pulang"  # preserved
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
        set_reason(conn, attendance_id=first["id"], category="lupa_absen_pulang", detail=None)

        open_ones = list_open_issues(conn)
        assert len(open_ones) == 1
        assert open_ones[0]["tanggal"] == "2026-04-03"


def test_list_employees_with_open_issues_counts_sorts_and_ranges(temp_db_path):
    """Grouped per-employee open counts: resolved rows, clean rows, and
    rows outside [start, end] must not count; result sorted by nama."""
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        budi = upsert_employee(conn, no_staff="9001", nama="BUDI",
                               dept="TEST", phone="081234567890")
        ani = upsert_employee(conn, no_staff="9002", nama="ANI", dept="OPS")
        citra = upsert_employee(conn, no_staff="9003", nama="CITRA", dept="OPS")
        # BUDI: 2 open in April + 1 open outside the range (May)
        _seed_issue(conn, budi, "2026-04-02", masuk="08.10")
        _seed_issue(conn, budi, "2026-04-03")
        _seed_issue(conn, budi, "2026-05-01")
        # ANI: 1 open + 1 resolved (resolved must not count)
        _seed_issue(conn, ani, "2026-04-06")
        _seed_issue(conn, ani, "2026-04-07", masuk="08.15")
        rid = conn.execute(
            "SELECT id FROM attendance_records WHERE employee_id=? AND tanggal='2026-04-07'",
            (ani,),
        ).fetchone()["id"]
        set_reason(conn, attendance_id=rid, category="lupa_absen_pulang", detail=None)
        # CITRA: clean row only -> excluded entirely
        _seed_issue(conn, citra, "2026-04-06", masuk="08.00", keluar="16.00",
                    has_issue=0)

        rows = list_employees_with_open_issues(conn, "2026-04-01", "2026-04-30")
        assert [r["nama"] for r in rows] == ["ANI", "BUDI"]
        by_name = {r["nama"]: r for r in rows}
        assert by_name["BUDI"]["open_cnt"] == 2
        assert by_name["ANI"]["open_cnt"] == 1
        assert by_name["BUDI"]["id"] == budi
        assert by_name["BUDI"]["phone"] == "081234567890"
        assert by_name["ANI"]["dept"] == "OPS"


def test_list_open_issues_for_employee_filters_and_orders(temp_db_path):
    """Only THAT employee's open rows inside [start, end], oldest first."""
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        budi = upsert_employee(conn, no_staff="9001", nama="BUDI", dept="TEST")
        ani = upsert_employee(conn, no_staff="9002", nama="ANI", dept="OPS")
        _seed_issue(conn, budi, "2026-04-09")                 # open, later date
        _seed_issue(conn, budi, "2026-04-02", masuk="08.10")  # open, earlier date
        _seed_issue(conn, budi, "2026-05-01")                 # outside range
        _seed_issue(conn, budi, "2026-04-05")                 # will be resolved
        _seed_issue(conn, ani, "2026-04-03")                  # other employee
        rid = conn.execute(
            "SELECT id FROM attendance_records WHERE employee_id=? AND tanggal='2026-04-05'",
            (budi,),
        ).fetchone()["id"]
        set_reason(conn, attendance_id=rid, category="cuti", detail=None)

        rows = list_open_issues_for_employee(conn, budi, "2026-04-01", "2026-04-30")
        assert [r["tanggal"] for r in rows] == ["2026-04-02", "2026-04-09"]
        assert rows[0]["masuk"] == "08.10"
        assert rows[0]["keluar"] is None
        assert set(rows[0].keys()) == {"tanggal", "hari", "masuk", "keluar"}
