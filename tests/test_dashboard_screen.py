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


def test_dashboard_query_cache_invalidated_by_data_version(temp_db_path, monkeypatch, tk_root):
    """A data change (bump) forces _query to refetch instead of serving the
    memoized result for the same period."""
    import src.ui.screens.dashboard as mod
    from src.core.session_state import notify_data_changed
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    _setup_db(temp_db_path)

    calls = {"n": 0}
    real = mod.terlambat_ranking
    def counting(conn, s, e):
        calls["n"] += 1
        return real(conn, s, e)
    monkeypatch.setattr(mod, "terlambat_ranking", counting)

    screen = mod.DashboardScreen(tk_root)          # __init__ -> _update_data -> _query (1 call)
    tk_root.update_idletasks()
    start, end, _ = screen._period_range()
    base = calls["n"]
    screen._query(start, end)                      # same period, no change -> cache hit
    assert calls["n"] == base
    notify_data_changed()
    screen._query(start, end)                      # version changed -> cache cleared -> refetch
    assert calls["n"] == base + 1
    screen.destroy()


def test_dashboard_on_show_resyncs_nav_from_period_state(temp_db_path, monkeypatch, tk_root):
    """A cached screen must pick up the session week chosen on another
    screen when it is re-displayed."""
    from src.core.session_state import period_state
    import src.ui.screens.dashboard as mod
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    _setup_db(temp_db_path)
    screen = mod.DashboardScreen(tk_root)
    tk_root.update_idletasks()
    assert screen.nav.active == "semua"
    period_state.set("minggu_3")   # changed elsewhere (e.g. Issues screen)
    screen.on_show()
    tk_root.update_idletasks()
    assert screen.nav.active == "minggu_3"
    screen.destroy()


def test_dashboard_on_show_picks_up_month_change(temp_db_path, monkeypatch, tk_root):
    """Active-month change made in Settings must reflect on re-display."""
    import src.ui.screens.dashboard as mod
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    _setup_db(temp_db_path)  # sets 2026-05
    screen = mod.DashboardScreen(tk_root)
    tk_root.update_idletasks()
    with get_connection(temp_db_path) as conn:
        set_setting(conn, "current_month", "2026-06")
    screen.on_show()
    tk_root.update_idletasks()
    assert screen._current_month == "2026-06"
    assert "2026-06" in screen._kpi_labels["periode"].cget("text")
    screen.destroy()
