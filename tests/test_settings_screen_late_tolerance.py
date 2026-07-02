# tests/test_settings_screen_late_tolerance.py
import src.ui.screens.settings as mod
from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.settings import get_setting


def test_settings_saves_late_tolerance(temp_db_path, monkeypatch, tk_root):
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    # _save() ends with feedback.show_info(); patch it or the modal blocks the test.
    monkeypatch.setattr(mod.feedback, "show_info", lambda *a, **k: None)
    init_db(temp_db_path)
    screen = mod.SettingsScreen(tk_root)
    tk_root.update_idletasks()
    assert hasattr(screen, "tol_var"), "tol_var entry must exist"
    screen.tol_var.set("20")
    screen._save()
    tk_root.update_idletasks()
    with get_connection(temp_db_path) as conn:
        assert get_setting(conn, "late_tolerance_min") == "20"
    screen.destroy()


def test_settings_rejects_out_of_range_tolerance(temp_db_path, monkeypatch, tk_root):
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    # silence the modal warning during the test
    monkeypatch.setattr(mod.feedback, "show_warning", lambda *a, **k: None)
    init_db(temp_db_path)
    screen = mod.SettingsScreen(tk_root)
    tk_root.update_idletasks()
    screen.tol_var.set("1000")   # above max 999 -> rejected, nothing saved
    screen._save()
    with get_connection(temp_db_path) as conn:
        assert get_setting(conn, "late_tolerance_min") == "12"
    screen.destroy()
