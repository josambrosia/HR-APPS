"""v26: Settings "Jam Kantor" berjadwal + Ambang Lembur."""
import pytest

from src.db.connection import get_connection
from src.db.schedule import list_periods
from src.db.schema import init_db
from src.db.settings import get_setting


@pytest.fixture
def env(tmp_path, monkeypatch):
    import src.ui.screens.settings as settings_mod
    dbp = tmp_path / "hr.db"
    init_db(dbp)
    monkeypatch.setattr(settings_mod, "DB_PATH", dbp)
    return settings_mod, dbp


def _screen(env, tk_root):
    settings_mod, dbp = env
    s = settings_mod.SettingsScreen(tk_root)
    tk_root.update_idletasks()
    return s


def test_screen_shows_current_schedule_and_history(env, tk_root):
    s = _screen(env, tk_root)
    try:
        text = s._sched_label.cget("text")
        assert "09.00" in text and "17.00" in text
        assert len(s._sched_list.winfo_children()) == 1
    finally:
        s.destroy()


def test_save_rejects_overtime_before_schedule_end(env, tk_root, monkeypatch):
    settings_mod, dbp = env
    warnings = []
    monkeypatch.setattr(settings_mod.feedback, "show_warning",
                        lambda *a, **k: warnings.append(a))
    monkeypatch.setattr(settings_mod.feedback, "show_info",
                        lambda *a, **k: None)
    s = _screen(env, tk_root)
    try:
        s.overtime_var.set("16.00")
        s._save()
        assert warnings
        with get_connection(dbp) as conn:
            assert get_setting(conn, "overtime_threshold") == "18.00"
    finally:
        s.destroy()


def test_save_rejects_malformed_overtime(env, tk_root, monkeypatch):
    settings_mod, dbp = env
    warnings = []
    monkeypatch.setattr(settings_mod.feedback, "show_warning",
                        lambda *a, **k: warnings.append(a))
    monkeypatch.setattr(settings_mod.feedback, "show_info",
                        lambda *a, **k: None)
    s = _screen(env, tk_root)
    try:
        s.overtime_var.set("jam enam")
        s._save()
        assert warnings
    finally:
        s.destroy()


def test_save_accepts_valid_overtime(env, tk_root, monkeypatch):
    settings_mod, dbp = env
    monkeypatch.setattr(settings_mod.feedback, "show_warning",
                        lambda *a, **k: None)
    monkeypatch.setattr(settings_mod.feedback, "show_info",
                        lambda *a, **k: None)
    s = _screen(env, tk_root)
    try:
        s.overtime_var.set("18.30")
        s._save()
        with get_connection(dbp) as conn:
            assert get_setting(conn, "overtime_threshold") == "18.30"
    finally:
        s.destroy()


def test_add_period_via_dialog(tmp_path, monkeypatch, tk_root):
    import src.ui.components.schedule_change_dialog as dlg_mod
    dbp = tmp_path / "hr.db"
    init_db(dbp)
    monkeypatch.setattr(dlg_mod, "DB_PATH", dbp)
    monkeypatch.setattr(dlg_mod.feedback, "show_warning",
                        lambda *a, **k: None)
    saved = []
    dlg = dlg_mod.ScheduleChangeDialog(tk_root, on_saved=lambda: saved.append(1))
    try:
        dlg._tanggal.delete(0, "end")
        dlg._tanggal.insert(0, "2999-12-01")
        dlg._masuk.delete(0, "end")
        dlg._masuk.insert(0, "08.00")
        dlg._keluar.delete(0, "end")
        dlg._keluar.insert(0, "16.00")
        dlg._save()
    finally:
        if dlg.winfo_exists():
            dlg.destroy()
    assert saved == [1]
    with get_connection(dbp) as conn:
        periods = list_periods(conn)
        assert periods[-1]["effective_from"] == "2999-12-01"
        assert periods[-1]["start_time"] == "08.00"


def test_dialog_rejects_past_date(tmp_path, monkeypatch, tk_root):
    import src.ui.components.schedule_change_dialog as dlg_mod
    dbp = tmp_path / "hr.db"
    init_db(dbp)
    monkeypatch.setattr(dlg_mod, "DB_PATH", dbp)
    warnings = []
    monkeypatch.setattr(dlg_mod.feedback, "show_warning",
                        lambda *a, **k: warnings.append(a))
    dlg = dlg_mod.ScheduleChangeDialog(tk_root, on_saved=lambda: None)
    try:
        dlg._tanggal.delete(0, "end")
        dlg._tanggal.insert(0, "2000-01-01")
        dlg._save()
        assert warnings
    finally:
        if dlg.winfo_exists():
            dlg.destroy()


def test_general_tab_scrollable_with_sticky_save(env, tk_root, monkeypatch):
    """Tab General bisa discroll dan tombol Simpan selalu terlihat (v26 fix:
    perubahan toleransi tampak 'tidak tersimpan' karena tombol terpotong)."""
    import customtkinter as ctk
    settings_mod, dbp = env
    monkeypatch.setattr(settings_mod.feedback, "show_info",
                        lambda *a, **k: None)
    monkeypatch.setattr(settings_mod.feedback, "show_warning",
                        lambda *a, **k: None)
    s = _screen(env, tk_root)
    try:
        assert isinstance(s._general_scroller, ctk.CTkScrollableFrame)
        assert len(s._general_scroller.winfo_children()) > 0
        # Tombol Simpan berada di bar sticky, bukan di dalam area scroll.
        assert s._save_btn.master is s._save_bar
        # Toleransi benar-benar tersimpan saat tombol dipakai.
        s.tol_var.set("25")
        s._save()
        with get_connection(dbp) as conn:
            assert get_setting(conn, "late_tolerance_min") == "25"
    finally:
        s.destroy()
