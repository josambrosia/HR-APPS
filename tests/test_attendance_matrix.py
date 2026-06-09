# tests/test_attendance_matrix.py
from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.attendance import upsert_attendance, list_attendance_matrix

def test_matrix_returns_rows_with_employee(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = upsert_employee(conn, no_staff="1", nama="ANDI", dept="IT")
        upsert_attendance(conn, employee_id=a, tanggal="2026-05-04", hari="Senin",
                          tipe="Hari Kerja", jadwal="08.00 - 16.00", masuk="09:15",
                          keluar="16:30", kerja_jam=None, lembur_jam=None,
                          terlambat_menit=75, has_issue=0, imported_from="W1.xls")
        rows = list_attendance_matrix(conn, "2026-05-01", "2026-05-31")
    assert len(rows) == 1
    r = rows[0]
    assert r["nama"] == "ANDI" and r["dept"] == "IT"
    assert r["tanggal"] == "2026-05-04" and r["terlambat_menit"] == 75
    assert r["reason_category"] is None and r["tipe"] == "Hari Kerja"

def test_matrix_filters_range(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = upsert_employee(conn, no_staff="1", nama="ANDI", dept="IT")
        for d in ("2026-04-30", "2026-05-15", "2026-06-01"):
            upsert_attendance(conn, employee_id=a, tanggal=d, hari="X",
                              tipe="Hari Kerja", jadwal="", masuk="08:00", keluar="16:00",
                              kerja_jam=None, lembur_jam=None, terlambat_menit=0,
                              has_issue=0, imported_from="W")
        rows = list_attendance_matrix(conn, "2026-05-01", "2026-05-31")
    assert [r["tanggal"] for r in rows] == ["2026-05-15"]
