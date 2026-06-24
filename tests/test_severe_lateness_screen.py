import customtkinter as ctk
from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.attendance import upsert_attendance
from src.db.settings import set_setting


def _seed(conn):
    a = upsert_employee(conn, no_staff="1", nama="BUDI", dept="IT")
    b = upsert_employee(conn, no_staff="2", nama="ANI", dept="HR")
    for eid, late in ((a, 75), (b, 90)):
        upsert_attendance(conn, employee_id=eid, tanggal="2026-05-04", hari="Senin",
                          tipe="Hari Kerja", jadwal="08.00 - 16.00",
                          masuk="09:15", keluar="16:30", kerja_jam=None,
                          lembur_jam=None, terlambat_menit=late, has_issue=0,
                          imported_from="W1.xls")
    set_setting(conn, "current_month", "2026-05")


def test_screen_constructs_with_batch_resolve(temp_db_path, monkeypatch, tk_root):
    import src.ui.screens.severe_lateness as mod
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        _seed(conn)
    screen = mod.SevereLatenessScreen(tk_root)
    tk_root.update_idletasks()
    assert hasattr(screen, "_on_batch_resolve")
    screen.destroy()


def test_screen_binds_ctrl_f(temp_db_path, monkeypatch, tk_root):
    import src.ui.screens.severe_lateness as mod
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    screen = mod.SevereLatenessScreen(tk_root)
    tk_root.update_idletasks()
    assert screen.bind("<Control-f>") != ""
    screen.destroy()


def test_screen_filter_reduces_rows(temp_db_path, monkeypatch, tk_root):
    import src.ui.screens.severe_lateness as mod
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        _seed(conn)
    screen = mod.SevereLatenessScreen(tk_root)
    tk_root.update_idletasks()
    assert len(screen.open_tree.get_children()) == 2
    screen._apply_filter("budi")
    tk_root.update_idletasks()
    assert len(screen.open_tree.get_children()) == 1
    screen._apply_filter("")
    tk_root.update_idletasks()
    assert len(screen.open_tree.get_children()) == 2
    screen.destroy()


def test_screen_reads_and_writes_period_state(temp_db_path, monkeypatch, tk_root):
    from src.core.session_state import period_state
    import src.ui.screens.severe_lateness as mod
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        set_setting(conn, "current_month", "2026-05")
    period_state.set("minggu_2")
    screen = mod.SevereLatenessScreen(tk_root)
    tk_root.update_idletasks()
    assert screen.nav.active == "minggu_2"
    screen._on_period_change("minggu_3")
    tk_root.update_idletasks()
    assert period_state.get() == "minggu_3"
    screen.destroy()


def test_severe_uses_searchbar_shortcuts_helper(temp_db_path, monkeypatch, tk_root):
    import src.ui.screens.severe_lateness as mod
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    screen = mod.SevereLatenessScreen(tk_root)
    tk_root.update_idletasks()
    assert getattr(screen._search, "_click_bind_id", None) is not None
    assert not hasattr(screen, "_on_click_outside_search")
    screen.destroy()
