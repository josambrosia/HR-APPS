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
