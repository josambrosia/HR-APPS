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
