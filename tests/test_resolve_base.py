"""v22 unification tests — Issues + Severe Lateness share ResolveScreenBase;
KPI cards update in place; the SearchBar debounce coalesces rapid
keystrokes into a single re-render."""
import time

from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.attendance import upsert_attendance
from src.db.settings import set_setting
from src.ui.components.search_bar import SearchBar
from src.ui.screens.resolve_base import ResolveScreenBase


def _seed_issues(conn):
    a = upsert_employee(conn, no_staff="1", nama="BUDI", dept="X")
    b = upsert_employee(conn, no_staff="2", nama="ANI", dept="Y")
    for eid in (a, b):
        upsert_attendance(
            conn, employee_id=eid, tanggal="2026-05-04", hari="Senin",
            tipe="Hari Kerja", jadwal="08.00 - 16.00",
            masuk=None, keluar="16:00", kerja_jam=None,
            lembur_jam=None, terlambat_menit=None,
            has_issue=1, imported_from="W1.xls",
        )
    set_setting(conn, "current_month", "2026-05")


def _pump_until(tk_root, cond, timeout=1.5):
    """Drive the Tk event loop (incl. `after` timers) until cond() or timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        tk_root.update()
        if cond():
            return True
        time.sleep(0.01)
    return bool(cond())


def test_both_screens_share_resolve_base(temp_db_path, monkeypatch, tk_root):
    import src.ui.screens.issues as issues_mod
    import src.ui.screens.severe_lateness as severe_mod
    monkeypatch.setattr(issues_mod, "DB_PATH", temp_db_path)
    monkeypatch.setattr(severe_mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        _seed_issues(conn)
    assert issubclass(issues_mod.IssuesScreen, ResolveScreenBase)
    assert issubclass(severe_mod.SevereLatenessScreen, ResolveScreenBase)
    for cls in (issues_mod.IssuesScreen, severe_mod.SevereLatenessScreen):
        screen = cls(tk_root)
        tk_root.update_idletasks()
        assert isinstance(screen, ResolveScreenBase)
        screen.destroy()


def test_kpi_cards_update_in_place_on_reload(temp_db_path, monkeypatch, tk_root):
    """_render_stats must reuse the 5 KPICard widgets built once in
    _build_stats — no destroy+recreate churn per reload."""
    import src.ui.screens.issues as mod
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        _seed_issues(conn)
    screen = mod.IssuesScreen(tk_root)
    tk_root.update_idletasks()
    cards_before = list(screen._stats_cards)
    assert len(cards_before) == 5
    # Open card shows the 2 seeded open issues
    assert screen._stats_cards[0]._value_label.cget("text") == "2"
    screen._reload()
    tk_root.update_idletasks()
    assert list(screen._stats_cards) == cards_before, \
        "reload must update the SAME card widgets, not rebuild them"
    assert screen._stats_cards[0]._value_label.cget("text") == "2"
    screen.destroy()


def test_debounced_search_coalesces_keystrokes(temp_db_path, monkeypatch, tk_root):
    """Three rapid keystrokes → ONE _render_rows call after the pause."""
    import src.ui.screens.issues as mod
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        _seed_issues(conn)
    screen = mod.IssuesScreen(tk_root)
    tk_root.update_idletasks()

    renders = []
    orig_render = screen._render_rows
    screen._render_rows = lambda q: (renders.append(q), orig_render(q))[1]

    sb = screen._search
    for ch in "bud":                       # rapid typing burst
        sb._entry.insert("end", ch)
        sb._on_key_release()
    assert renders == [], "debounced keystrokes must not render synchronously"

    assert _pump_until(tk_root, lambda: renders), \
        "debounced search never fired"
    assert renders == ["bud"], f"expected ONE coalesced render, got {renders}"
    assert len(screen.open_tree.get_children()) == 1   # BUDI only
    screen.destroy()


def test_apply_filter_skips_rerender_for_same_effective_query(
        temp_db_path, monkeypatch, tk_root):
    import src.ui.screens.issues as mod
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        _seed_issues(conn)
    screen = mod.IssuesScreen(tk_root)
    tk_root.update_idletasks()

    renders = []
    orig_render = screen._render_rows
    screen._render_rows = lambda q: (renders.append(q), orig_render(q))[1]

    screen._apply_filter("budi")
    assert renders == ["budi"]
    screen._apply_filter("budi ")   # same effective query (whitespace)
    screen._apply_filter("BUDI")    # same effective query (case)
    assert renders == ["budi"], "unchanged effective query must not re-render"
    screen._apply_filter("")
    assert renders == ["budi", ""]
    screen.destroy()


def test_searchbar_debounce_flush_and_default_immediate(tk_root):
    # debounce > 0: keystroke does NOT fire synchronously; Escape-flush and
    # clear() deliver immediately without waiting out the timer.
    events = []
    sb = SearchBar(tk_root, on_change=events.append, debounce_ms=5000)
    sb._entry.insert("end", "abc")
    sb._on_key_release()
    assert events == []
    sb._flush_pending()             # Escape path
    assert events == ["abc"]
    sb._entry.insert("end", "d")
    sb._on_key_release()
    sb.clear()                      # cancels the pending "abcd", fires "" now
    assert events == ["abc", ""]
    sb.destroy()

    # default debounce_ms=0: existing callers keep per-keystroke behavior
    events2 = []
    sb2 = SearchBar(tk_root, on_change=events2.append)
    sb2._entry.insert("end", "x")
    sb2._on_key_release()
    assert events2 == ["x"]
    sb2.destroy()
