"""Smoke + behaviour test for the Settings screen."""
from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.settings import get_setting, set_setting


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


def test_settings_screen_loads_saved_lupa_penalty(temp_db_path, monkeypatch, tk_root):
    import src.ui.screens.settings as settings_mod
    monkeypatch.setattr(settings_mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        from src.db.settings import set_setting
        set_setting(conn, "lupa_absen_datang_penalty_min", "30")
    screen = settings_mod.SettingsScreen(tk_root)
    tk_root.update_idletasks()
    assert screen.lupa_penalty_var.get() == "30"
    screen.destroy()


def test_settings_screen_saves_hr_officer_name(temp_db_path, monkeypatch, tk_root):
    import src.ui.screens.settings as settings_mod
    monkeypatch.setattr(settings_mod, "DB_PATH", temp_db_path)
    monkeypatch.setattr(settings_mod.messagebox, "showinfo", lambda *a, **k: None)
    init_db(temp_db_path)
    screen = settings_mod.SettingsScreen(tk_root)
    tk_root.update_idletasks()
    screen.hr_name_var.set("Supriyadi, S.E.")
    screen._save_profil()
    with get_connection(temp_db_path) as conn:
        assert get_setting(conn, "hr_officer_name") == "Supriyadi, S.E."
    screen.destroy()


def test_settings_screen_loads_saved_hr_officer_name(temp_db_path, monkeypatch, tk_root):
    import src.ui.screens.settings as settings_mod
    monkeypatch.setattr(settings_mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        from src.db.settings import set_setting
        set_setting(conn, "hr_officer_name", "Budi Hartono")
    screen = settings_mod.SettingsScreen(tk_root)
    tk_root.update_idletasks()
    assert screen.hr_name_var.get() == "Budi Hartono"
    screen.destroy()


def test_settings_screen_saves_threshold_per_day(temp_db_path, monkeypatch, tk_root):
    """Edit thr_var and save → coaching_threshold_per_day persists."""
    import src.ui.screens.settings as settings_mod
    monkeypatch.setattr(settings_mod, "DB_PATH", temp_db_path)
    monkeypatch.setattr(settings_mod.messagebox, "showinfo", lambda *a, **k: None)
    init_db(temp_db_path)
    screen = settings_mod.SettingsScreen(tk_root)
    tk_root.update_idletasks()
    screen.thr_var.set("12")
    screen._save()
    with get_connection(temp_db_path) as conn:
        assert get_setting(conn, "coaching_threshold_per_day") == "12"
    screen.destroy()


def test_settings_screen_loads_saved_threshold_per_day(temp_db_path, monkeypatch, tk_root):
    """Pre-seed coaching_threshold_per_day → screen populates thr_var with it."""
    import src.ui.screens.settings as settings_mod
    monkeypatch.setattr(settings_mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        from src.db.settings import set_setting
        set_setting(conn, "coaching_threshold_per_day", "18")
    screen = settings_mod.SettingsScreen(tk_root)
    tk_root.update_idletasks()
    assert screen.thr_var.get() == "18"
    screen.destroy()


def test_save_rejects_lupa_penalty_negative(temp_db_path, monkeypatch, tk_root):
    """Negative penalty values must be rejected, settings unchanged."""
    import src.ui.screens.settings as mod
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        set_setting(conn, "lupa_absen_datang_penalty_min", "15")
    monkeypatch.setattr(mod.messagebox, "showinfo", lambda *a, **k: None)
    warnings = []
    monkeypatch.setattr(
        mod.messagebox, "showwarning",
        lambda *a, **k: warnings.append(a))
    screen = mod.SettingsScreen(tk_root)
    screen.lupa_penalty_var.set("-1")
    screen._save()
    with get_connection(temp_db_path) as conn:
        assert get_setting(conn, "lupa_absen_datang_penalty_min") == "15"  # unchanged
    assert len(warnings) == 1  # showwarning called once


def test_save_rejects_lupa_penalty_too_large(temp_db_path, monkeypatch, tk_root):
    """Penalty values above 999 must be rejected, settings unchanged."""
    import src.ui.screens.settings as mod
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        set_setting(conn, "lupa_absen_datang_penalty_min", "15")
    monkeypatch.setattr(mod.messagebox, "showinfo", lambda *a, **k: None)
    monkeypatch.setattr(mod.messagebox, "showwarning", lambda *a, **k: None)
    screen = mod.SettingsScreen(tk_root)
    screen.lupa_penalty_var.set("1000")
    screen._save()
    with get_connection(temp_db_path) as conn:
        assert get_setting(conn, "lupa_absen_datang_penalty_min") == "15"  # unchanged


def test_save_rejects_lupa_penalty_non_integer(temp_db_path, monkeypatch, tk_root):
    """Non-integer string (letters, decimals) must be rejected, settings unchanged."""
    import src.ui.screens.settings as mod
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        set_setting(conn, "lupa_absen_datang_penalty_min", "15")
    monkeypatch.setattr(mod.messagebox, "showinfo", lambda *a, **k: None)
    monkeypatch.setattr(mod.messagebox, "showwarning", lambda *a, **k: None)
    screen = mod.SettingsScreen(tk_root)
    screen.lupa_penalty_var.set("abc")
    screen._save()
    with get_connection(temp_db_path) as conn:
        assert get_setting(conn, "lupa_absen_datang_penalty_min") == "15"


def test_save_accepts_lupa_penalty_zero(temp_db_path, monkeypatch, tk_root):
    """Zero (no penalty) must be accepted."""
    import src.ui.screens.settings as mod
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    monkeypatch.setattr(mod.messagebox, "showinfo", lambda *a, **k: None)
    screen = mod.SettingsScreen(tk_root)
    screen.lupa_penalty_var.set("0")
    screen._save()
    with get_connection(temp_db_path) as conn:
        assert get_setting(conn, "lupa_absen_datang_penalty_min") == "0"
