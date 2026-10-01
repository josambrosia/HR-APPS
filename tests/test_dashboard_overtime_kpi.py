"""v26: KPI 'Lembur Belum Diproses' di Dashboard."""
from src.db.attendance import upsert_attendance
from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.schema import init_db
from src.db.settings import set_setting


def _seed(p):
    init_db(p)
    with get_connection(p) as conn:
        set_setting(conn, "current_month", "2026-10")
        e = upsert_employee(conn, no_staff="1", nama="Agus")
        upsert_attendance(
            conn, employee_id=e, tanggal="2026-10-01", hari=None,
            tipe="Hari Kerja", jadwal=None, masuk="09:00", keluar="19:30",
            kerja_jam=None, lembur_jam=None, terlambat_menit=0,
            has_issue=0, imported_from="t")


def test_kpi_shows_pending_count(tmp_path, monkeypatch, tk_root):
    import src.ui.screens.dashboard as mod
    p = tmp_path / "d.db"
    _seed(p)
    monkeypatch.setattr(mod, "DB_PATH", p)
    s = mod.DashboardScreen(tk_root)
    tk_root.update_idletasks()
    try:
        assert s._kpi_labels["overtime_pending"].cget("text") == "1"
    finally:
        s.destroy()


def test_kpi_zero_without_overtime(tmp_path, monkeypatch, tk_root):
    import src.ui.screens.dashboard as mod
    p = tmp_path / "d.db"
    init_db(p)
    with get_connection(p) as conn:
        set_setting(conn, "current_month", "2026-10")
    monkeypatch.setattr(mod, "DB_PATH", p)
    s = mod.DashboardScreen(tk_root)
    tk_root.update_idletasks()
    try:
        assert s._kpi_labels["overtime_pending"].cget("text") == "0"
    finally:
        s.destroy()
