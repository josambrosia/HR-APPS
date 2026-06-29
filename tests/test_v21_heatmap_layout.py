import pytest
from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.attendance import upsert_attendance
from src.db.settings import set_setting
import src.ui.screens.heatmap as mod


def test_heatmap_screen_one_column(tmp_path, monkeypatch, tk_root):
    # Set up an isolated DB with one employee so _repaint has real data
    p = tmp_path / "h.db"
    init_db(p)
    with get_connection(p) as conn:
        set_setting(conn, "current_month", "2026-05")
        a = upsert_employee(conn, no_staff="1", nama="ANDI", dept="IT")
        upsert_attendance(conn, employee_id=a, tanggal="2026-05-04", hari="Senin",
                          tipe="Hari Kerja", jadwal="", masuk="08:05", keluar="16:30",
                          kerja_jam=None, lembur_jam=None, terlambat_menit=5,
                          has_issue=0, imported_from="W")
    monkeypatch.setattr(mod, "DB_PATH", p)
    screen = mod.HeatmapScreen(tk_root)
    screen._repaint()
    assert screen._ncols == 1
    screen.destroy()
