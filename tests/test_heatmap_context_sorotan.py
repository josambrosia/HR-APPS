# tests/test_heatmap_context_sorotan.py
import tempfile
import os
from pathlib import Path
from datetime import date

from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.attendance import upsert_attendance
from src.core.heatmap import build_heatmap_context


def _seed(conn):
    a = upsert_employee(conn, no_staff="1", nama="ANDI", dept="IT")
    # Mon 75min -> TB(parah), Tue 20min -> TR(sedang), Wed 5min -> H(hadir)
    for tgl, hari, masuk, telat in (("2026-05-04", "Senin", "09:15", 75),
                                    ("2026-05-05", "Selasa", "08:20", 20),
                                    ("2026-05-06", "Rabu", "08:05", 5)):
        upsert_attendance(conn, employee_id=a, tanggal=tgl, hari=hari,
                          tipe="Hari Kerja", jadwal="", masuk=masuk, keluar="16:30",
                          kerja_jam=None, lembur_jam=None, terlambat_menit=telat,
                          has_issue=0, imported_from="W")
    return a


def _db():
    fd, p = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    p = Path(p)
    init_db(p)
    return p


def test_sorotan_metrics():
    p = _db()
    with get_connection(p) as conn:
        _seed(conn)
        ctx = build_heatmap_context(conn, "2026-05", exclude_outliers=False)
    e = ctx["employees"][0]
    s = e["sorotan"]
    assert s["hk"] == 3
    assert s["work_days"] == ctx["eff_hari_kerja"]
    assert s["ontime_days"] == 1
    assert s["telat_total"] == 95
    assert s["telat_days"] == 2
    assert s["pct_hadir"] == round(3 / ctx["eff_hari_kerja"] * 100)
    assert s["pct_color"] in ("#10B981", "#FBBF24", "#EC4899")
    assert e["needs_attention"] is True


def test_today_day_present_and_absent():
    p = _db()
    with get_connection(p) as conn:
        _seed(conn)
        in_month = build_heatmap_context(conn, "2026-05", exclude_outliers=False,
                                         today=date(2026, 5, 15))
        other = build_heatmap_context(conn, "2026-05", exclude_outliers=False,
                                      today=date(2026, 6, 1))
    assert in_month["today_day"] == 15
    assert other["today_day"] is None
