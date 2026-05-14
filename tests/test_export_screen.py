"""Smoke test for the restructured Export screen."""
from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.attendance import upsert_attendance
from src.db.settings import set_setting


def test_export_screen_constructs_with_modes(temp_db_path, monkeypatch, tk_root):
    import src.ui.screens.export as export_mod
    monkeypatch.setattr(export_mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = upsert_employee(conn, no_staff="1", nama="ANDI", dept="X")
        upsert_attendance(
            conn, employee_id=a, tanggal="2026-04-01", hari="Senin",
            tipe="Hari Kerja", jadwal="08.00 - 16.00", masuk="08.05",
            keluar="16.00", kerja_jam=8.0, lembur_jam=None,
            terlambat_menit=5, has_issue=0, imported_from="W1.xls",
        )
        set_setting(conn, "current_month", "2026-04")
        conn.commit()
    screen = export_mod.ExportScreen(tk_root)
    tk_root.update_idletasks()
    # both modes switchable without error
    screen._show_mode("generate")
    tk_root.update_idletasks()
    screen._show_mode("export")
    tk_root.update_idletasks()
    assert screen is not None
    screen.destroy()
