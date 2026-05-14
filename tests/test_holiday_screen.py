"""Smoke test for the Hari Libur screen — constructs without error against
a temp DB. Deep behaviour is covered by tests/test_holidays_db.py."""
from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.attendance import upsert_attendance
from src.db.settings import set_setting
from src.db.holidays import mark_holidays


def test_holiday_screen_constructs(temp_db_path, monkeypatch, tk_root):
    import src.ui.screens.holiday as holiday_mod
    monkeypatch.setattr(holiday_mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = upsert_employee(conn, no_staff="1", nama="ANDI", dept="X")
        upsert_attendance(
            conn, employee_id=a, tanggal="2026-04-01", hari="Senin",
            tipe="Hari Kerja", jadwal="08.00 - 16.00", masuk="08.05",
            keluar="16.00", kerja_jam=8.0, lembur_jam=None,
            terlambat_menit=5, has_issue=0, imported_from="W1.xls",
        )
        upsert_attendance(
            conn, employee_id=a, tanggal="2026-04-03", hari="Jumat",
            tipe="Hari Kerja", jadwal="08.00 - 16.00", masuk=None,
            keluar=None, kerja_jam=None, lembur_jam=None,
            terlambat_menit=None, has_issue=1, imported_from="W1.xls",
        )
        set_setting(conn, "current_month", "2026-04")
        mark_holidays(conn, ["2026-04-03"])
        conn.commit()
    screen = holiday_mod.HolidayScreen(tk_root)
    tk_root.update_idletasks()
    assert screen is not None
    screen.destroy()


def test_holiday_screen_constructs_no_active_month(temp_db_path, monkeypatch, tk_root):
    import src.ui.screens.holiday as holiday_mod
    monkeypatch.setattr(holiday_mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    screen = holiday_mod.HolidayScreen(tk_root)
    tk_root.update_idletasks()
    assert screen is not None
    screen.destroy()
