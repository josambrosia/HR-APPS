"""Tests for src.ui.screens.coaching — cross-screen state wiring."""
from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.settings import set_setting


def _setup_db(path):
    init_db(path)
    with get_connection(path) as conn:
        set_setting(conn, "current_month", "2026-05")


def test_coaching_reads_period_state_when_minggu_set(temp_db_path, monkeypatch, tk_root):
    """If period_state holds a minggu_N key, Coaching shows that week."""
    from src.core.session_state import period_state
    import src.ui.screens.coaching as mod
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    _setup_db(temp_db_path)
    period_state.set("minggu_2")
    screen = mod.CoachingScreen(tk_root)
    tk_root.update_idletasks()
    assert screen.nav.active == "minggu_2"
    screen.destroy()


def test_coaching_falls_back_to_minggu_1_when_state_is_semua(temp_db_path, monkeypatch, tk_root):
    """include_all=False means 'semua' isn't a rendered pill — the WeekNavBar
    falls back internally to minggu_1, but period_state stays 'semua' so
    Issues/Dashboard still show Semua if user navigates back."""
    from src.core.session_state import period_state
    import src.ui.screens.coaching as mod
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    _setup_db(temp_db_path)
    period_state.reset()  # back to "semua"
    screen = mod.CoachingScreen(tk_root)
    tk_root.update_idletasks()
    assert screen.nav.active == "minggu_1"  # internal fallback
    assert period_state.get() == "semua"     # shared state untouched
    screen.destroy()


def test_coaching_writes_period_state_on_change(temp_db_path, monkeypatch, tk_root):
    from src.core.session_state import period_state
    import src.ui.screens.coaching as mod
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    _setup_db(temp_db_path)
    screen = mod.CoachingScreen(tk_root)
    tk_root.update_idletasks()
    screen._on_period_change("minggu_3")
    tk_root.update_idletasks()
    assert period_state.get() == "minggu_3"
    screen.destroy()


def test_coaching_on_show_resyncs_nav_and_threshold(temp_db_path, monkeypatch, tk_root):
    """on_show re-reads month/threshold and re-syncs the pills. With
    include_all=False, a session 'semua' falls back to minggu_1 exactly
    like __init__ does."""
    from src.core.session_state import period_state
    import src.ui.screens.coaching as mod
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    _setup_db(temp_db_path)
    period_state.set("minggu_2")
    screen = mod.CoachingScreen(tk_root)
    tk_root.update_idletasks()
    assert screen.nav.active == "minggu_2"
    period_state.reset()  # back to "semua" (chosen on another screen)
    with get_connection(temp_db_path) as conn:
        set_setting(conn, "coaching_threshold_per_day", "25")
    screen.on_show()
    tk_root.update_idletasks()
    assert screen.nav.active == "minggu_1"   # internal fallback, same as __init__
    assert screen._daily_threshold == 25     # threshold re-read from DB
    screen.destroy()
