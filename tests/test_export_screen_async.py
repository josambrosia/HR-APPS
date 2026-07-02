"""v22 Export screen — background workers + BusyGuard wiring.

Worker bodies (export_fill_work, preview_fill_work, generate_*_work) are
module-level and Tk-free — tested synchronously against a temp DB.
Screen flows are tested with run_bg monkeypatched AS IMPORTED in
src.ui.screens.export to a synchronous fake (no real thread), plus
feedback.show_* / show_success_toast patched where dialogs would block.
"""
from pathlib import Path

from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.attendance import upsert_attendance, set_reason
from src.db.settings import set_setting
from src.db.export_history import list_recent_exports
from src.core.report_filler import FillSummary
import src.ui.screens.export as export_mod


def _seed_april(db_path):
    """BUDI with the 3 April days matching the synthetic_monthly_xlsx fixture:
    01 clean, 02 open issue, 03 resolved issue (izin_sakit)."""
    init_db(db_path)
    with get_connection(db_path) as conn:
        b = upsert_employee(conn, no_staff="9001", nama="BUDI", dept="TEST")
        upsert_attendance(
            conn, employee_id=b, tanggal="2026-04-01", hari="Senin",
            tipe="Hari Kerja", jadwal="08.00 - 16.00", masuk="08:05",
            keluar="16:30", kerja_jam=7.9, lembur_jam=None,
            terlambat_menit=5, has_issue=0, imported_from="W1.xls",
        )
        upsert_attendance(
            conn, employee_id=b, tanggal="2026-04-02", hari="Selasa",
            tipe="Hari Kerja", jadwal="08.00 - 16.00", masuk="08:10",
            keluar=None, kerja_jam=None, lembur_jam=None,
            terlambat_menit=10, has_issue=1, imported_from="W1.xls",
        )
        upsert_attendance(
            conn, employee_id=b, tanggal="2026-04-03", hari="Rabu",
            tipe="Hari Kerja", jadwal="08.00 - 16.00", masuk=None,
            keluar=None, kerja_jam=None, lembur_jam=None,
            terlambat_menit=None, has_issue=1, imported_from="W1.xls",
        )
        row_id = conn.execute(
            "SELECT id FROM attendance_records WHERE tanggal='2026-04-03'"
        ).fetchone()["id"]
        set_reason(conn, attendance_id=row_id, category="izin_sakit", detail=None)
        set_setting(conn, "current_month", "2026-04")


def _sync_run_bg(widget, work, *, on_done, on_error=None, on_progress=None, poll_ms=50):
    """Synchronous stand-in for run_bg — runs work inline, then the callback."""
    try:
        result = work(lambda *a, **k: None)
    except Exception as exc:
        if on_error is None:
            raise
        on_error(exc)
    else:
        on_done(result)


# ── Module-level workers (no Tk) ──


def test_export_fill_work_writes_file_and_history(temp_db_path, synthetic_monthly_xlsx, tmp_path):
    _seed_april(temp_db_path)
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    out_path, summary = export_mod.export_fill_work(
        temp_db_path, synthetic_monthly_xlsx, out_dir,
    )

    assert out_path.exists()
    assert out_path.parent == out_dir
    # 04-03 resolved → filled; 04-02 open issue → NA; 04-01 clean → skipped
    assert summary.filled_count == 1
    assert summary.na_count == 1
    assert summary.not_found_count == 0
    with get_connection(temp_db_path) as conn:
        items = list_recent_exports(conn)
    assert len(items) == 1
    assert items[0]["kind"] == "fill"
    assert items[0]["year_month"] == "2026-04"
    assert items[0]["out_path"] == str(out_path)
    assert items[0]["template"] == str(synthetic_monthly_xlsx)


def test_preview_fill_work_generates_into_tmp_dir_without_history(
    temp_db_path, synthetic_monthly_xlsx, tmp_path,
):
    _seed_april(temp_db_path)
    tmp_dir = tmp_path / "hr-preview-x"  # does not exist yet — worker mkdirs it

    out_path = export_mod.preview_fill_work(temp_db_path, synthetic_monthly_xlsx, tmp_dir)

    assert out_path.exists()
    assert out_path.parent == tmp_dir
    with get_connection(temp_db_path) as conn:
        assert list_recent_exports(conn) == []  # preview leaves no history


def test_generate_bulanan_work_creates_file_and_history(temp_db_path, tmp_path):
    _seed_april(temp_db_path)
    out = tmp_path / "Laporan Bulanan April 2026 [Auto Filled].xlsx"

    summary = export_mod.generate_bulanan_work(temp_db_path, "2026-04", out)

    assert out.exists()
    assert summary.rows_generated == 3
    with get_connection(temp_db_path) as conn:
        items = list_recent_exports(conn)
    assert len(items) == 1
    assert items[0]["kind"] == "generate_bulanan"
    assert items[0]["year_month"] == "2026-04"
    assert items[0]["filled"] == 3


def test_generate_mingguan_work_creates_file_and_history(temp_db_path, tmp_path):
    _seed_april(temp_db_path)
    out = tmp_path / "Laporan Mingguan 2026-03-30 sd 2026-04-05.xlsx"

    summary = export_mod.generate_mingguan_work(
        temp_db_path, "2026-03-30", "2026-04-05", out,
    )

    assert out.exists()
    assert summary.rows == 3
    with get_connection(temp_db_path) as conn:
        items = list_recent_exports(conn)
    assert len(items) == 1
    assert items[0]["kind"] == "generate_mingguan"
    assert items[0]["year_month"] == "2026-03"  # week start month


# ── Screen flows (run_bg patched to synchronous fake) ──


def test_do_export_flow_updates_ui_and_releases_guard(
    temp_db_path, synthetic_monthly_xlsx, monkeypatch, tk_root,
):
    monkeypatch.setattr(export_mod, "DB_PATH", temp_db_path)
    _seed_april(temp_db_path)
    monkeypatch.setattr(export_mod, "run_bg", _sync_run_bg)

    screen = export_mod.ExportScreen(tk_root)
    tk_root.update_idletasks()
    screen._selected = synthetic_monthly_xlsx
    screen._show_chip(synthetic_monthly_xlsx, predicted_out_name="laporan [filled].xlsx")
    tk_root.update_idletasks()

    screen._do_export()
    tk_root.update_idletasks()

    # Guard released, buttons restored
    assert screen._chip_export_btn.cget("state") == "normal"
    assert screen._chip_export_btn.cget("text") == "💾 Export"
    # Result strip rendered + history written
    assert screen.result_frame.winfo_children()
    with get_connection(temp_db_path) as conn:
        items = list_recent_exports(conn)
    assert len(items) == 1
    assert items[0]["kind"] == "fill"
    screen.destroy()


def test_do_export_double_click_is_noop_while_busy(
    temp_db_path, synthetic_monthly_xlsx, monkeypatch, tk_root, tmp_path,
):
    monkeypatch.setattr(export_mod, "DB_PATH", temp_db_path)
    _seed_april(temp_db_path)

    calls = []

    def deferred_run_bg(widget, work, *, on_done, on_error=None, on_progress=None, poll_ms=50):
        calls.append((work, on_done))  # hold — simulates an in-flight worker

    monkeypatch.setattr(export_mod, "run_bg", deferred_run_bg)
    stub_result = (tmp_path / "out.xlsx", FillSummary(1, 0, 0))
    monkeypatch.setattr(export_mod, "export_fill_work", lambda *a, **k: stub_result)

    screen = export_mod.ExportScreen(tk_root)
    screen._selected = synthetic_monthly_xlsx
    screen._show_chip(synthetic_monthly_xlsx)
    tk_root.update_idletasks()

    screen._do_export()
    assert len(calls) == 1
    # Busy: clicked primary shows busy text, sibling actions disabled too
    assert screen._chip_export_btn.cget("text") == "Memproses…"
    assert screen._chip_export_btn.cget("state") == "disabled"
    assert screen._chip_preview_btn.cget("state") == "disabled"
    assert screen._chip_ganti_btn.cget("state") == "disabled"

    screen._do_export()  # double-click while busy
    assert len(calls) == 1  # no second worker spawned

    work, on_done = calls[0]
    on_done(work(lambda *a, **k: None))  # worker "finishes" on the main thread
    tk_root.update_idletasks()
    assert screen._chip_export_btn.cget("text") == "💾 Export"
    assert screen._chip_export_btn.cget("state") == "normal"

    screen._do_export()  # guard released → next click spawns again
    assert len(calls) == 2
    screen.destroy()


def test_do_export_error_releases_guard_and_shows_error(
    temp_db_path, synthetic_monthly_xlsx, monkeypatch, tk_root,
):
    monkeypatch.setattr(export_mod, "DB_PATH", temp_db_path)
    _seed_april(temp_db_path)
    monkeypatch.setattr(export_mod, "run_bg", _sync_run_bg)

    def boom(*a, **k):
        raise RuntimeError("disk penuh")

    monkeypatch.setattr(export_mod, "export_fill_work", boom)
    errors = []
    monkeypatch.setattr(
        export_mod.feedback, "show_error",
        lambda parent, title, msg: errors.append((title, msg)),
    )

    screen = export_mod.ExportScreen(tk_root)
    screen._selected = synthetic_monthly_xlsx
    screen._show_chip(synthetic_monthly_xlsx)
    tk_root.update_idletasks()

    screen._do_export()

    assert errors == [("Error export", "disk penuh")]
    assert screen._chip_export_btn.cget("state") == "normal"
    screen.destroy()


def test_generate_mingguan_flow_generates_and_releases_guard(
    temp_db_path, monkeypatch, tk_root, tmp_path,
):
    monkeypatch.setattr(export_mod, "DB_PATH", temp_db_path)
    _seed_april(temp_db_path)
    monkeypatch.setattr(export_mod, "run_bg", _sync_run_bg)
    toasts = []
    monkeypatch.setattr(
        export_mod, "show_success_toast", lambda *a, **k: toasts.append((a, k)),
    )
    out_file = tmp_path / "mingguan.xlsx"
    monkeypatch.setattr(
        export_mod.filedialog, "asksaveasfilename", lambda **k: str(out_file),
    )

    screen = export_mod.ExportScreen(tk_root)
    screen._show_mode("generate")
    screen._show_gen_sub("mingguan")
    tk_root.update_idletasks()

    screen._on_generate_mingguan()
    tk_root.update_idletasks()

    assert out_file.exists()
    assert len(toasts) == 1
    assert screen._gen_mingguan_btn.cget("state") == "normal"
    assert screen._gen_mingguan_btn.cget("text") == "⚙ Generate Laporan Mingguan"
    with get_connection(temp_db_path) as conn:
        assert list_recent_exports(conn)[0]["kind"] == "generate_mingguan"
    screen.destroy()


def test_generate_mingguan_cancel_dialog_releases_guard(
    temp_db_path, monkeypatch, tk_root,
):
    monkeypatch.setattr(export_mod, "DB_PATH", temp_db_path)
    _seed_april(temp_db_path)
    spawned = []
    monkeypatch.setattr(
        export_mod, "run_bg", lambda *a, **k: spawned.append(a),
    )
    monkeypatch.setattr(
        export_mod.filedialog, "asksaveasfilename", lambda **k: "",  # user cancels
    )

    screen = export_mod.ExportScreen(tk_root)
    screen._show_mode("generate")
    screen._show_gen_sub("mingguan")
    tk_root.update_idletasks()

    screen._on_generate_mingguan()

    assert spawned == []  # no worker
    assert screen._gen_mingguan_btn.cget("state") == "normal"  # guard released
    assert screen._busy_guard is not None and not screen._busy_guard.busy
    screen.destroy()
