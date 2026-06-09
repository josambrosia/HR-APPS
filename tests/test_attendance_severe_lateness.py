# tests/test_attendance_severe_lateness.py
from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.attendance import (
    upsert_attendance, set_reason,
    list_severe_lateness_for_period, count_severe_lateness_for_period,
)

START, END = "2026-05-01", "2026-05-31"


def _seed(conn):
    a = upsert_employee(conn, no_staff="1", nama="BUDI", dept="IT")
    b = upsert_employee(conn, no_staff="2", nama="ANI", dept="HR")
    # BUDI: 75 min late, both punches -> severe
    upsert_attendance(conn, employee_id=a, tanggal="2026-05-04", hari="Senin",
                      tipe="Hari Kerja", jadwal="08.00 - 16.00",
                      masuk="09:15", keluar="16:30", kerja_jam=None,
                      lembur_jam=None, terlambat_menit=75, has_issue=0,
                      imported_from="W1.xls")
    # ANI: 30 min late -> below threshold 60
    upsert_attendance(conn, employee_id=b, tanggal="2026-05-05", hari="Selasa",
                      tipe="Hari Kerja", jadwal="08.00 - 16.00",
                      masuk="08:30", keluar="16:05", kerja_jam=None,
                      lembur_jam=None, terlambat_menit=30, has_issue=0,
                      imported_from="W1.xls")
    # BUDI: 120 min late but MISSING keluar -> this is an Issue, not severe-late
    upsert_attendance(conn, employee_id=a, tanggal="2026-05-06", hari="Rabu",
                      tipe="Hari Kerja", jadwal="08.00 - 16.00",
                      masuk="10:00", keluar=None, kerja_jam=None,
                      lembur_jam=None, terlambat_menit=120, has_issue=1,
                      imported_from="W1.xls")
    return a, b


def test_list_filters_by_threshold(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        _seed(conn)
        rows = list_severe_lateness_for_period(conn, START, END, 60)
        names = [r["nama"] for r in rows]
        assert names == ["BUDI"]  # only the 75-min, both-punches row


def test_list_excludes_missing_punch_rows(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        _seed(conn)
        rows = list_severe_lateness_for_period(conn, START, END, 60)
        for r in rows:
            assert r["masuk"] and r["keluar"]


def test_list_open_vs_resolved_split(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a, _ = _seed(conn)
        # resolve BUDI's severe row
        row = list_severe_lateness_for_period(conn, START, END, 60)[0]
        set_reason(conn, attendance_id=row["id"], category="terlambat_lain",
                   detail="macet")
        assert list_severe_lateness_for_period(conn, START, END, 60, resolved=False) == []
        resolved = list_severe_lateness_for_period(conn, START, END, 60, resolved=True)
        assert len(resolved) == 1


def test_count_open_resolved_na_total(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        _seed(conn)
        c = count_severe_lateness_for_period(conn, START, END, 60)
        assert c == {"open": 1, "resolved": 0, "na": 0, "total": 1}
        row = list_severe_lateness_for_period(conn, START, END, 60)[0]
        set_reason(conn, attendance_id=row["id"], category="na", detail=None)
        c2 = count_severe_lateness_for_period(conn, START, END, 60)
        assert c2 == {"open": 0, "resolved": 0, "na": 1, "total": 1}
