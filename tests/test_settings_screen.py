"""Smoke + behaviour test for the Settings screen."""
from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.settings import get_setting


def test_settings_screen_constructs(temp_db_path, monkeypatch, tk_root):
    import src.ui.screens.settings as settings_mod
    monkeypatch.setattr(settings_mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    screen = settings_mod.SettingsScreen(tk_root)
    tk_root.update_idletasks()
    assert screen is not None
    screen.destroy()


def test_settings_screen_saves_lupa_penalty(temp_db_path, monkeypatch, tk_root):
    import src.ui.screens.settings as settings_mod
    monkeypatch.setattr(settings_mod, "DB_PATH", temp_db_path)
    monkeypatch.setattr(settings_mod.messagebox, "showinfo", lambda *a, **k: None)
    init_db(temp_db_path)
    screen = settings_mod.SettingsScreen(tk_root)
    tk_root.update_idletasks()
    screen.lupa_penalty_var.set("25")
    screen._save()
    with get_connection(temp_db_path) as conn:
        assert get_setting(conn, "lupa_absen_datang_penalty_min") == "25"
    screen.destroy()
