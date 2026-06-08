"""Smoke test for the Issues screen — constructs + Batch Resolve wired."""
from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.attendance import upsert_attendance
from src.db.settings import set_setting


def test_issues_screen_constructs_with_batch_resolve(temp_db_path, monkeypatch, tk_root):
    import src.ui.screens.issues as issues_mod
    monkeypatch.setattr(issues_mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = upsert_employee(conn, no_staff="1", nama="ANDI", dept="X")
        upsert_attendance(
            conn, employee_id=a, tanggal="2026-04-01", hari="Senin",
            tipe="Hari Kerja", jadwal="08.00 - 16.00",
            masuk=None, keluar="16:00", kerja_jam=None,
            lembur_jam=None, terlambat_menit=None,
            has_issue=1, imported_from="W1.xls",
        )
        set_setting(conn, "current_month", "2026-04")
        conn.commit()
    screen = issues_mod.IssuesScreen(tk_root)
    tk_root.update_idletasks()
    assert screen is not None
    assert hasattr(screen, "_on_batch_resolve")
    screen.destroy()


def test_issues_screen_reads_period_state_on_mount(temp_db_path, monkeypatch, tk_root):
    """When period_state holds a week key, the screen's WeekNavBar
    should reflect it on mount."""
    from src.core.session_state import period_state
    import src.ui.screens.issues as mod
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        set_setting(conn, "current_month", "2026-05")
    period_state.set("minggu_2")
    screen = mod.IssuesScreen(tk_root)
    tk_root.update_idletasks()
    assert screen.nav.active == "minggu_2"
    screen.destroy()


def test_issues_screen_writes_period_state_on_change(temp_db_path, monkeypatch, tk_root):
    """Clicking a pill should update period_state so other screens see it."""
    from src.core.session_state import period_state
    import src.ui.screens.issues as mod
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        set_setting(conn, "current_month", "2026-05")
    screen = mod.IssuesScreen(tk_root)
    tk_root.update_idletasks()
    screen._on_period_change("minggu_3")
    tk_root.update_idletasks()
    assert period_state.get() == "minggu_3"
    screen.destroy()


def test_issues_screen_binds_ctrl_f(temp_db_path, monkeypatch, tk_root):
    """Structural: the Ctrl-f binding exists on the screen frame.
    Actual focus side effect is verified by manual smoke per project
    policy (headless tkinter doesn't move focus reliably)."""
    import src.ui.screens.issues as mod
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    screen = mod.IssuesScreen(tk_root)
    tk_root.update_idletasks()
    bindings = screen.bind("<Control-f>")
    assert bindings != "", "Ctrl+F binding should be present on IssuesScreen"
    screen.destroy()


def test_issues_resolve_panel_binds_return(temp_db_path, monkeypatch, tk_root):
    """When an issue is selected the right-panel form binds Return → _on_save."""
    from src.db.settings import set_setting
    import src.ui.screens.issues as mod
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = upsert_employee(conn, no_staff="1", nama="ANDI", dept="X")
        upsert_attendance(
            conn, employee_id=a, tanggal="2026-04-07", hari="Selasa",
            tipe="Hari Kerja", jadwal="08.00 - 16.00",
            masuk=None, keluar="16:00", kerja_jam=None,
            lembur_jam=None, terlambat_menit=None,
            has_issue=1, imported_from="W1.xls",
        )
        set_setting(conn, "current_month", "2026-04")
        conn.commit()
    screen = mod.IssuesScreen(tk_root)
    tk_root.update_idletasks()
    # Simulate selecting the first open issue to build the form panel
    children = screen.open_tree.get_children()
    assert children, "Expected at least one open issue row"
    screen.open_tree.selection_set(children[0])
    screen._on_select_open(None)
    tk_root.update_idletasks()
    # After selection the right panel should bind Return
    assert screen.right.bind("<Return>") != "", (
        "Return binding must be present on the right panel after issue selection")
    screen.destroy()


def test_issues_apply_filter_reduces_visible_rows(temp_db_path, monkeypatch, tk_root):
    """Setting a filter query that doesn't match anyone hides all rows;
    setting one that matches one employee shows only that employee."""
    import src.ui.screens.issues as mod
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        set_setting(conn, "current_month", "2026-05")
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
    screen = mod.IssuesScreen(tk_root)
    tk_root.update_idletasks()
    assert len(screen.open_tree.get_children()) == 2
    screen._apply_filter("budi")
    tk_root.update_idletasks()
    visible = screen.open_tree.get_children()
    assert len(visible) == 1
    screen._apply_filter("")
    tk_root.update_idletasks()
    assert len(screen.open_tree.get_children()) == 2
    screen.destroy()
