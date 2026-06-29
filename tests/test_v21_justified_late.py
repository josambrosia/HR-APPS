import os, tempfile
from pathlib import Path
from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.attendance import upsert_attendance, set_reason

def _db():
    fd, p = tempfile.mkstemp(suffix=".db"); os.close(fd); p = Path(p)
    init_db(p)
    return p

def _att(conn, eid, tgl, hari, *, masuk, keluar, telat):
    upsert_attendance(conn, employee_id=eid, tanggal=tgl, hari=hari,
                      tipe="Hari Kerja", jadwal="", masuk=masuk, keluar=keluar,
                      kerja_jam=None, lembur_jam=None, terlambat_menit=telat,
                      has_issue=0, imported_from="W")

def _reason(conn, eid, tgl, cat):
    aid = conn.execute(
        "SELECT id FROM attendance_records WHERE employee_id=? AND tanggal=?",
        (eid, tgl)).fetchone()[0]
    set_reason(conn, attendance_id=aid, category=cat, detail=None)


from src.core.heatmap import cell_status
from src.core.insights import terlambat_ranking, top_n_terlambat
from src.core.reason_mapper import effective_attendance

def _row(**kw):
    base = {"tipe": "Hari Kerja", "reason_category": None,
            "masuk": "08:30", "keluar": "16:30", "terlambat_menit": 30}
    base.update(kw)
    return base

def test_cell_status_terlambat_lain_dinas_with_punch():
    r = _row(reason_category="terlambat_lain")
    assert cell_status(r, tolerance=12, severe=60,
                       is_weekend=False, is_holiday=False) == "dinas"

def test_cell_status_terlambat_lain_dinas_without_punch():
    r = _row(reason_category="terlambat_lain", masuk=None, keluar=None,
             terlambat_menit=None)
    assert cell_status(r, tolerance=12, severe=60,
                       is_weekend=False, is_holiday=False) == "dinas"

def test_effective_attendance_terlambat_lain_zeroed():
    r = _row(reason_category="terlambat_lain")
    eff = effective_attendance(r, schedule_start="08.00", lupa_penalty_min=15)
    assert eff["terlambat_menit"] == 0 and eff["masuk"] == "08:00"

def test_ranking_terlambat_lain_zero_minutes():
    with get_connection(_db()) as conn:
        e = upsert_employee(conn, no_staff="1", nama="ANDI", dept="IT")
        _att(conn, e, "2026-05-04", "Senin", masuk="08:30", keluar="16:30", telat=30)
        _reason(conn, e, "2026-05-04", "terlambat_lain")
        row = terlambat_ranking(conn, "2026-05-01", "2026-05-31")[0]
        top = top_n_terlambat(conn, "2026-05-01", "2026-05-31")
    assert row["total_terlambat"] == 0
    assert row["hari_telat"] == 0
    assert top == []


def test_ranking_terlambat_lain_no_punch_not_absent():
    with get_connection(_db()) as conn:
        e = upsert_employee(conn, no_staff="1", nama="ANDI", dept="IT")
        _att(conn, e, "2026-05-04", "Senin", masuk=None, keluar=None, telat=None)
        _reason(conn, e, "2026-05-04", "terlambat_lain")
        row = terlambat_ranking(conn, "2026-05-01", "2026-05-31")[0]
    assert row["tidak_hadir"] == 0
    assert row["absent_count"] == 0
