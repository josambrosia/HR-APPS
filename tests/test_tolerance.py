"""v26: toleransi keterlambatan berlaku per tanggal (riwayat)."""
import sqlite3

from src.core.heatmap import build_heatmap_context
from src.db.attendance import upsert_attendance
from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.schema import init_db
from src.db.settings import get_setting
from src.db.tolerance import (add_period, current_tolerance, list_periods,
                              tolerance_for)


def test_fresh_db_seeds_single_period(tmp_path):
    p = tmp_path / "t.db"
    init_db(p)
    with get_connection(p) as conn:
        periods = list_periods(conn)
        assert len(periods) == 1
        assert periods[0]["effective_from"] == "1970-01-01"
        assert periods[0]["tolerance_min"] == 12
        assert tolerance_for(conn, "2026-01-01") == 12


def test_legacy_custom_setting_seeds_period(tmp_path):
    p = tmp_path / "t.db"
    with sqlite3.connect(p) as conn:
        conn.execute("CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute("INSERT INTO settings VALUES ('late_tolerance_min','20')")
        conn.commit()
    init_db(p)
    with get_connection(p) as conn:
        assert list_periods(conn)[0]["tolerance_min"] == 20
        assert tolerance_for(conn, "2026-01-01") == 20


def test_add_period_boundaries_and_mirror(tmp_path):
    p = tmp_path / "t.db"
    init_db(p)
    with get_connection(p) as conn:
        add_period(conn, effective_from="2026-10-15", tolerance_min=15)
        assert tolerance_for(conn, "2026-10-14") == 12
        assert tolerance_for(conn, "2026-10-15") == 15
        assert get_setting(conn, "late_tolerance_min") == "15"


def test_current_tolerance_uses_active_period(tmp_path):
    p = tmp_path / "t.db"
    init_db(p)
    with get_connection(p) as conn:
        add_period(conn, effective_from="1970-01-02", tolerance_min=15)
        assert current_tolerance(conn) == 15


def test_add_period_upserts_same_date(tmp_path):
    p = tmp_path / "t.db"
    init_db(p)
    with get_connection(p) as conn:
        add_period(conn, effective_from="2026-10-15", tolerance_min=15)
        add_period(conn, effective_from="2026-10-15", tolerance_min=18)
        periods = list_periods(conn)
        assert len(periods) == 2
        assert periods[-1]["tolerance_min"] == 18


def test_heatmap_uses_per_date_tolerance(tmp_path):
    """Bulan yang melintasi perubahan: tanggal lama pakai nilai lama."""
    p = tmp_path / "t.db"
    init_db(p)
    with get_connection(p) as conn:
        eid = upsert_employee(conn, no_staff="1", nama="Agus")
        for tgl in ("2026-10-05", "2026-10-20"):
            upsert_attendance(
                conn, employee_id=eid, tanggal=tgl, hari=None,
                tipe="Hari Kerja", jadwal=None, masuk="08:13", keluar="16:00",
                kerja_jam=7.8, lembur_jam=None, terlambat_menit=13,
                has_issue=0, imported_from="t")
        add_period(conn, effective_from="2026-10-15", tolerance_min=15)
        ctx = build_heatmap_context(conn, "2026-10", exclude_outliers=False)
    emp = ctx["employees"][0]
    assert emp["cells"][5]["status"] == "sedang"   # 13 > 12 (toleransi lama)
    assert emp["cells"][20]["status"] == "hadir"   # 13 <= 15 (toleransi baru)
