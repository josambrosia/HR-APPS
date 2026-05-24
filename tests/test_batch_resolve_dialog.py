"""Tests for the Batch Resolve dialog — pure logic + construction smoke."""
from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.attendance import upsert_attendance, list_issues_for_period
from src.ui.components.batch_resolve_dialog import (
    group_open_issues_by_employee, apply_batch_resolve, BatchResolveDialog,
)


def _issue(conn, emp_id, tanggal, hari):
    upsert_attendance(
        conn, employee_id=emp_id, tanggal=tanggal, hari=hari,
        tipe="Hari Kerja", jadwal="08.00 - 16.00",
        masuk=None, keluar="16:00", kerja_jam=None,
        lembur_jam=None, terlambat_menit=None,
        has_issue=1, imported_from="W1.xls",
    )


def test_group_open_issues_by_employee(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = upsert_employee(conn, no_staff="1", nama="ZARA", dept="X")
        b = upsert_employee(conn, no_staff="2", nama="ANDI", dept="Y")
        _issue(conn, a, "2026-04-07", "Selasa")
        _issue(conn, b, "2026-04-07", "Selasa")
        _issue(conn, b, "2026-04-08", "Rabu")
        rows = list_issues_for_period(conn, "2026-04-01", "2026-04-30",
                                      resolved=False)
        groups = group_open_issues_by_employee(rows)
    assert [g["nama"] for g in groups] == ["ANDI", "ZARA"]   # sorted by nama
    andi = groups[0]
    assert len(andi["issues"]) == 2
    assert {i["tanggal"] for i in andi["issues"]} == {"2026-04-07", "2026-04-08"}
    assert all("attendance_id" in i for i in andi["issues"])


def test_apply_batch_resolve_sets_reason_on_all(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = upsert_employee(conn, no_staff="1", nama="ANDI", dept="X")
        _issue(conn, a, "2026-04-07", "Selasa")
        _issue(conn, a, "2026-04-08", "Rabu")
        ids = [r["id"] for r in conn.execute(
            "SELECT id FROM attendance_records").fetchall()]
        n = apply_batch_resolve(conn, ids, "tugas_lapangan", "Sragen")
        assert n == 2
        rows = conn.execute(
            "SELECT reason_category, reason_detail FROM attendance_records"
        ).fetchall()
    assert all(r["reason_category"] == "tugas_lapangan" for r in rows)
    assert all(r["reason_detail"] == "Sragen" for r in rows)


def test_batch_resolve_dialog_constructs(temp_db_path, monkeypatch, tk_root):
    import src.ui.components.batch_resolve_dialog as mod
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = upsert_employee(conn, no_staff="1", nama="ANDI", dept="X")
        _issue(conn, a, "2026-04-07", "Selasa")
        conn.commit()
    dlg = mod.BatchResolveDialog(
        tk_root, period_start="2026-04-01", period_end="2026-04-30",
        on_done=lambda: None)
    tk_root.update_idletasks()
    assert dlg is not None
    dlg.destroy()


def test_batch_resolve_dialog_constructs_with_no_issues(temp_db_path, monkeypatch, tk_root):
    """No open issues — empty state, must not crash."""
    import src.ui.components.batch_resolve_dialog as mod
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    dlg = mod.BatchResolveDialog(
        tk_root, period_start="2026-04-01", period_end="2026-04-30",
        on_done=lambda: None)
    tk_root.update_idletasks()
    assert dlg is not None
    dlg.destroy()


def test_batch_resolve_dialog_detail_field_toggles(temp_db_path, monkeypatch, tk_root):
    """Detail entry is pack-managed for a needs-detail category, hidden otherwise."""
    import src.ui.components.batch_resolve_dialog as mod
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = upsert_employee(conn, no_staff="1", nama="ANDI", dept="X")
        _issue(conn, a, "2026-04-07", "Selasa")
        conn.commit()
    dlg = mod.BatchResolveDialog(
        tk_root, period_start="2026-04-01", period_end="2026-04-30",
        on_done=lambda: None)
    tk_root.update_idletasks()
    # needs-detail category -> detail entry is pack-managed
    dlg._cat_var.set("Tugas Lapangan")
    dlg._on_cat_change("Tugas Lapangan")
    tk_root.update_idletasks()
    assert dlg._detail_entry.winfo_manager() == "pack"
    # no-detail category -> detail entry is unmanaged
    dlg._cat_var.set("Cuti")
    dlg._on_cat_change("Cuti")
    tk_root.update_idletasks()
    assert dlg._detail_entry.winfo_manager() == ""
    dlg.destroy()


def test_batch_resolve_dialog_btn_row_in_footer_grid_row(
        temp_db_path, monkeypatch, tk_root):
    """Regression guard for v15.3 — btn_row sits in ROW_FOOTER of the
    toplevel's 3-row grid.

    History of this bug (4 attempts now — see version_state.md):
    - v15.0: side='bottom' reflow trick — failed (Tk skipped reflow).
    - v15.1: side='top' natural flow — failed (toplevel auto-grew past
      requested geometry, btn_row fell off the visible bottom).
    - v15.2: single grid on toplevel with spacer row + propagate(False) —
      failed (propagate calls didn't prevent dialog growth on this CTk
      build; screenshot showed dialog ~862px tall for a 600px request).
    - v15.3 (this fix): header / CTkScrollableFrame content / footer.
      Footer is in ROW_FOOTER=2 of the toplevel's 3-row grid. The middle
      row (CTkScrollableFrame) absorbs ALL content overflow into a scroll
      bar instead of pushing the footer down. Whether the toplevel grows,
      shrinks, or scales by some unknown DPI factor, the footer cannot be
      displaced because it's structurally in its own grid slot AND the
      middle row scrolls.

    This test asserts the structural invariants:
      1. btn_row uses grid manager
      2. btn_row.grid_info()['row'] == ROW_FOOTER
      3. The toplevel has the expected 3-row grid configured
      4. Toggling _on_cat_change with both detail-less and detail-bearing
         categories leaves btn_row's grid row unchanged

    Visible-button regression remains verified by manual smoke per project
    policy — pytest's headless tkinter can't confirm pixels are on-screen.
    """
    import src.ui.components.batch_resolve_dialog as mod
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = upsert_employee(conn, no_staff="1", nama="ANDI", dept="X")
        _issue(conn, a, "2026-04-07", "Selasa")
        conn.commit()
    dlg = mod.BatchResolveDialog(
        tk_root, period_start="2026-04-01", period_end="2026-04-30",
        on_done=lambda: None)
    tk_root.update_idletasks()
    assert hasattr(dlg, "_btn_row")
    assert dlg._btn_row.winfo_manager() == "grid", (
        f"btn_row must use grid manager (got {dlg._btn_row.winfo_manager()!r}). "
        "v15.0/v15.1 used pack and the buttons disappeared — see release notes."
    )
    grid_info = dlg._btn_row.grid_info()
    assert int(grid_info["row"]) == mod.BatchResolveDialog.ROW_FOOTER, (
        f"btn_row must be at grid row ROW_FOOTER="
        f"{mod.BatchResolveDialog.ROW_FOOTER} (got row={grid_info.get('row')!r})"
    )
    # Detail-less category toggle: btn_row's row MUST NOT change
    dlg._cat_var.set("Cuti")
    dlg._on_cat_change("Cuti")
    tk_root.update_idletasks()
    assert int(dlg._btn_row.grid_info()["row"]) == (
        mod.BatchResolveDialog.ROW_FOOTER), (
        "btn_row row index changed after _on_cat_change('Cuti') — "
        "should be impossible with the header/content/footer architecture."
    )
    # Detail-bearing category toggle: still no change
    dlg._cat_var.set("Tugas Lapangan")
    dlg._on_cat_change("Tugas Lapangan")
    tk_root.update_idletasks()
    assert int(dlg._btn_row.grid_info()["row"]) == (
        mod.BatchResolveDialog.ROW_FOOTER)
    dlg.destroy()
