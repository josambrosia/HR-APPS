"""Tests for src.ui.screens.dashboard — cross-screen state wiring."""
from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.settings import set_setting


def _setup_db(path):
    init_db(path)
    with get_connection(path) as conn:
        set_setting(conn, "current_month", "2026-05")


def test_dashboard_screen_reads_period_state_on_mount(temp_db_path, monkeypatch, tk_root):
    from src.core.session_state import period_state
    import src.ui.screens.dashboard as mod
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    _setup_db(temp_db_path)
    period_state.set("minggu_2")
    screen = mod.DashboardScreen(tk_root)
    tk_root.update_idletasks()
    assert screen.nav.active == "minggu_2"
    screen.destroy()


def test_dashboard_screen_writes_period_state_on_change(temp_db_path, monkeypatch, tk_root):
    from src.core.session_state import period_state
    import src.ui.screens.dashboard as mod
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    _setup_db(temp_db_path)
    screen = mod.DashboardScreen(tk_root)
    tk_root.update_idletasks()
    screen._on_period_change("minggu_4")
    tk_root.update_idletasks()
    assert period_state.get() == "minggu_4"
    screen.destroy()
