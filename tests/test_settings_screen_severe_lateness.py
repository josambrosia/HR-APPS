# tests/test_settings_screen_severe_lateness.py
import src.ui.screens.settings as mod
from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.settings import get_setting


def test_settings_saves_severe_threshold(temp_db_path, monkeypatch, tk_root):
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    screen = mod.SettingsScreen(tk_root)
    tk_root.update_idletasks()
    assert hasattr(screen, "severe_var"), "severe_var entry must exist"
    screen.severe_var.set("90")
    screen._save()
    tk_root.update_idletasks()
    with get_connection(temp_db_path) as conn:
        assert get_setting(conn, "severe_lateness_threshold_min") == "90"
    screen.destroy()


def test_settings_rejects_out_of_range(temp_db_path, monkeypatch, tk_root):
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    # silence the modal warning during the test
    monkeypatch.setattr(mod.messagebox, "showwarning", lambda *a, **k: None)
    init_db(temp_db_path)
    screen = mod.SettingsScreen(tk_root)
    tk_root.update_idletasks()
    screen.severe_var.set("0")   # below min 1 -> rejected, nothing saved
    screen._save()
    with get_connection(temp_db_path) as conn:
        assert get_setting(conn, "severe_lateness_threshold_min") == "60"
    screen.destroy()
