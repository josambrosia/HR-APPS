"""v22 shell navigation — cached screen instances, on_show contract,
and WeekNavBar.sync for persistent bars.

HRApp._show is exercised through a minimal harness object (real _show +
_create_screen logic, stubbed sidebar hooks) so no second Tk root window
is created alongside the session-scoped tk_root fixture.
"""
import customtkinter as ctk

from src.core.week_utils import weeks_in_month
from src.db.schema import init_db
from src.ui.app import HRApp
from src.ui.components.week_nav import WeekNavBar


class _ShellHarness:
    """Stand-in for HRApp carrying exactly the state _show() needs."""

    _show = HRApp._show
    _create_screen = HRApp._create_screen

    def __init__(self, root):
        self.content = ctk.CTkFrame(root)
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)
        self._screens = {}
        self._visible_name = ""

    # Sidebar hooks — irrelevant to the caching contract.
    def _refresh_active_month_label(self):
        pass

    def _set_active_nav_item(self, name):
        pass

    def _show_about(self):
        pass

    def destroy(self):
        self.content.destroy()


def _make_shell(tk_root, temp_db_path, monkeypatch):
    init_db(temp_db_path)
    import src.ui.screens.dashboard as dash_mod
    import src.ui.screens.issues as issues_mod
    monkeypatch.setattr(dash_mod, "DB_PATH", temp_db_path)
    monkeypatch.setattr(issues_mod, "DB_PATH", temp_db_path)
    return _ShellHarness(tk_root)


def _gridded_names(shell):
    return {str(w) for w in shell.content.grid_slaves()}


def test_screens_cached_hidden_not_destroyed(tk_root, temp_db_path, monkeypatch):
    shell = _make_shell(tk_root, temp_db_path, monkeypatch)
    try:
        shell._show("Dashboard")
        dash1 = shell._screens["Dashboard"]
        assert str(dash1) in _gridded_names(shell)

        shell._show("Issues")
        issues1 = shell._screens["Issues"]
        # Dashboard is hidden (grid_remove), NOT destroyed.
        assert dash1.winfo_exists()
        assert str(dash1) not in _gridded_names(shell)
        assert str(issues1) in _gridded_names(shell)

        shell._show("Dashboard")
        # Same instances on return — no rebuild.
        assert shell._screens["Dashboard"] is dash1
        assert shell._screens["Issues"] is issues1
        assert issues1.winfo_exists()
        assert str(dash1) in _gridded_names(shell)
        assert str(issues1) not in _gridded_names(shell)
    finally:
        shell.destroy()


def test_on_show_fires_on_redisplay_not_first_build(
    tk_root, temp_db_path, monkeypatch,
):
    shell = _make_shell(tk_root, temp_db_path, monkeypatch)
    try:
        shell._show("Dashboard")
        calls = []
        shell._screens["Dashboard"].on_show = lambda: calls.append("dash")
        assert calls == []  # first build: __init__ rendered, no on_show

        shell._show("Issues")
        assert calls == []

        shell._show("Dashboard")
        assert calls == ["dash"]

        # Re-clicking the active nav item refreshes the visible screen.
        shell._show("Dashboard")
        assert calls == ["dash", "dash"]
    finally:
        shell.destroy()


def test_week_nav_sync_rebuilds_pills_silently(tk_root):
    fired = []
    nav = WeekNavBar(
        tk_root, current_month="2026-06", on_change=fired.append,
    )
    try:
        keys_jun = {f"minggu_{n}" for n, _s, _e in weeks_in_month("2026-06")}
        keys_jun.add("semua")
        assert set(nav._buttons) == keys_jun

        # Same month: only the active key moves; on_change never fires.
        nav.sync("2026-06", "minggu_2")
        assert nav.active == "minggu_2"
        assert fired == []

        # Month change: pills rebuilt for the new month, active key kept.
        nav.sync("2026-07", "minggu_2")
        keys_jul = {f"minggu_{n}" for n, _s, _e in weeks_in_month("2026-07")}
        keys_jul.add("semua")
        assert set(nav._buttons) == keys_jul
        assert nav.active == "minggu_2"
        assert fired == []

        # Unknown key falls back to the first rendered pill (same rule
        # as __init__), still silent.
        nav.sync("2026-07", "minggu_99")
        assert nav.active in nav._buttons
        assert fired == []
    finally:
        nav.destroy()
