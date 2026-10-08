"""v26: Settings — toleransi berjadwal (berlaku mulai tanggal)."""
from datetime import date

import pytest

from src.db.connection import get_connection
from src.db.schema import init_db
from src.db.settings import get_setting
from src.db.tolerance import list_periods


@pytest.fixture
def env(tmp_path, monkeypatch):
    import src.ui.screens.settings as settings_mod
    dbp = tmp_path / "hr.db"
    init_db(dbp)
    monkeypatch.setattr(settings_mod, "DB_PATH", dbp)
    monkeypatch.setattr(settings_mod.feedback, "show_info", lambda *a, **k: None)
    monkeypatch.setattr(settings_mod.feedback, "show_warning",
                        lambda *a, **k: warnings.append(a))
    warnings = []
    return settings_mod, dbp, warnings


def _screen(env, tk_root):
    settings_mod, dbp, _ = env
    s = settings_mod.SettingsScreen(tk_root)
    tk_root.update_idletasks()
    return s


def test_save_tolerance_creates_period_with_date(env, tk_root):
    settings_mod, dbp, warnings = env
    s = _screen(env, tk_root)
    try:
        today = date.today().isoformat()
        s.tol_var.set("15")
        s.tol_date_var.set(today)
        s._save()
        assert warnings == []
        with get_connection(dbp) as conn:
            periods = list_periods(conn)
            assert periods[-1]["effective_from"] == today
            assert periods[-1]["tolerance_min"] == 15
            assert get_setting(conn, "late_tolerance_min") == "15"
        assert "berlaku sejak" in s._tol_note.cget("text")
    finally:
        s.destroy()


def test_save_tolerance_past_date_rejected(env, tk_root):
    settings_mod, dbp, warnings = env
    s = _screen(env, tk_root)
    try:
        s.tol_var.set("15")
        s.tol_date_var.set("2000-01-01")
        s._save()
        assert warnings
        with get_connection(dbp) as conn:
            assert len(list_periods(conn)) == 1
    finally:
        s.destroy()


def test_save_tolerance_malformed_date_rejected(env, tk_root):
    settings_mod, dbp, warnings = env
    s = _screen(env, tk_root)
    try:
        s.tol_var.set("15")
        s.tol_date_var.set("besok")
        s._save()
        assert warnings
        with get_connection(dbp) as conn:
            assert len(list_periods(conn)) == 1
    finally:
        s.destroy()


def test_save_same_value_does_not_add_period(env, tk_root):
    settings_mod, dbp, warnings = env
    s = _screen(env, tk_root)
    try:
        s.tol_var.set("12")   # sama dengan nilai berjalan
        s._save()
        with get_connection(dbp) as conn:
            assert len(list_periods(conn)) == 1
    finally:
        s.destroy()


def test_save_correction_same_date_updates_period(env, tk_root):
    settings_mod, dbp, warnings = env
    s = _screen(env, tk_root)
    try:
        today = date.today().isoformat()
        s.tol_var.set("15")
        s.tol_date_var.set(today)
        s._save()
        s.tol_var.set("18")
        s.tol_date_var.set(today)
        s._save()
        with get_connection(dbp) as conn:
            periods = list_periods(conn)
            assert len(periods) == 2
            assert periods[-1]["tolerance_min"] == 18
    finally:
        s.destroy()
