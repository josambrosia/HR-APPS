"""Tests for the reworked Import screen (v22) — background parse/confirm
via run_bg + componentized banner / chip / history.

Async flows are tested by monkeypatching run_bg AS IMPORTED IN
import_screen with a synchronous fake that runs work(progress) inline and
then fires the terminal callback — no threads, no Tk-loop pumping.
feedback.show_* is patched the same way older screen tests patch
messagebox (see tests/test_settings_screen_late_tolerance.py).
"""
import pytest

import src.ui.screens.import_screen as mod
from src.db.attendance import set_reason
from src.db.connection import get_connection
from src.db.schema import init_db
from src.db.settings import get_setting, set_setting
from src.parsers.fingerprint import FingerprintRow


def _sync_run_bg(widget, work, *, on_done, on_error=None, on_progress=None,
                 poll_ms=50):
    """Synchronous run_bg stand-in: work(progress) inline, then on_done."""

    def progress(current, total, label=None):
        if on_progress is not None:
            on_progress(current, total, label)

    try:
        result = work(progress)
    except Exception as exc:
        if on_error is not None:
            on_error(exc)
            return None
        raise
    on_done(result)
    return None


def _fp_row(no_staff: str, nama: str, tanggal: str) -> FingerprintRow:
    return FingerprintRow(
        nama=nama, no_staff=no_staff, dept="TEST", tanggal=tanggal,
        hari="Senin", tipe="Hari Kerja", jadwal="08.00 - 16.00",
        masuk="08.00", keluar="16.00", kerja_jam=8.0, lembur_jam=None,
        terlambat_menit=0, source_file="w1.xls",
    )


def _make_screen(temp_db_path, monkeypatch, tk_root):
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    screen = mod.ImportScreen(tk_root)
    tk_root.update_idletasks()
    return screen


def _all_text(widget):
    """Recursively gather every text fragment in the widget tree."""
    out = []
    try:
        text = widget.cget("text")
        if text:
            out.append(str(text))
    except Exception:
        pass
    for child in widget.winfo_children():
        out.extend(_all_text(child))
    return out


# ── parse-phase worker function ──

def test_parse_import_files_returns_rows_and_progress(synthetic_fingerprint_xls):
    events = []
    result = mod.parse_import_files(
        [synthetic_fingerprint_xls],
        progress=lambda c, t, label=None: events.append((c, t, label)),
    )
    assert len(result["rows"]) == 5  # matches the parser fixture tests
    assert result["parse_ms"] >= 0
    assert events == [(1, 1, synthetic_fingerprint_xls.name)]


def test_parse_import_files_propagates_parse_errors(tmp_path):
    with pytest.raises(Exception):
        mod.parse_import_files([tmp_path / "tidak_ada.xls"])


# ── confirm-phase worker function ──

def test_run_import_confirm_inserts_rows_and_sets_month(
        temp_db_path, synthetic_fingerprint_xls):
    init_db(temp_db_path)
    rows = mod.parse_import_files([synthetic_fingerprint_xls])["rows"]
    result = mod.run_import_confirm(temp_db_path, rows)
    assert result == {"row_count": 5, "mode_month": "2026-04"}
    with get_connection(temp_db_path) as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM attendance_records").fetchone()[0]
        assert count == 5
        assert get_setting(conn, "current_month") == "2026-04"


def test_run_import_confirm_preserves_reasons_on_reimport(
        temp_db_path, synthetic_fingerprint_xls):
    init_db(temp_db_path)
    rows = mod.parse_import_files([synthetic_fingerprint_xls])["rows"]
    mod.run_import_confirm(temp_db_path, rows)
    with get_connection(temp_db_path) as conn:
        rec = conn.execute(
            "SELECT id FROM attendance_records WHERE tanggal='2026-04-02'"
        ).fetchone()
        set_reason(conn, attendance_id=rec["id"],
                   category="sakit", detail="demam")
    # Re-import the same rows — upsert must keep the user-owned fields.
    mod.run_import_confirm(temp_db_path, rows)
    with get_connection(temp_db_path) as conn:
        rec = conn.execute(
            "SELECT reason_category, reason_detail, resolved_at "
            "FROM attendance_records WHERE tanggal='2026-04-02'"
        ).fetchone()
        assert rec["reason_category"] == "sakit"
        assert rec["reason_detail"] == "demam"
        assert rec["resolved_at"] is not None
        count = conn.execute(
            "SELECT COUNT(*) FROM attendance_records").fetchone()[0]
        assert count == 5  # upserted in place, not duplicated


def test_run_import_confirm_reports_progress_every_10_rows(temp_db_path):
    init_db(temp_db_path)
    rows = [_fp_row("9001", "BUDI", f"2026-04-{d:02d}") for d in range(1, 26)]
    events = []
    mod.run_import_confirm(
        temp_db_path, rows,
        progress=lambda done, total, label=None: events.append((done, total)),
    )
    assert events == [(0, 25), (10, 25), (20, 25)]


def test_run_import_confirm_rolls_back_whole_txn_on_error(
        temp_db_path, monkeypatch):
    init_db(temp_db_path)

    def boom(conn):
        raise RuntimeError("restamp meledak")

    monkeypatch.setattr(mod, "restamp_holidays", boom)
    with pytest.raises(RuntimeError):
        mod.run_import_confirm(
            temp_db_path, [_fp_row("9001", "BUDI", "2026-04-01")])
    with get_connection(temp_db_path) as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM attendance_records").fetchone()[0]
        assert count == 0  # nothing committed
        assert conn.execute(
            "SELECT COUNT(*) FROM employees").fetchone()[0] == 0
        assert get_setting(conn, "current_month") is None


# ── screen wiring (sync run_bg fake) ──

def test_ingest_then_confirm_end_to_end(
        temp_db_path, monkeypatch, tk_root, synthetic_fingerprint_xls):
    screen = _make_screen(temp_db_path, monkeypatch, tk_root)
    monkeypatch.setattr(mod, "run_bg", _sync_run_bg)
    toasts = []
    monkeypatch.setattr(mod, "show_success_toast",
                        lambda parent, **kw: toasts.append(kw))

    screen._ingest_paths([synthetic_fingerprint_xls])
    tk_root.update_idletasks()
    assert len(screen._pending_rows) == 5
    assert screen.chip.winfo_manager() == "pack"  # chip shown
    assert screen.dropzone.winfo_manager() == ""  # dropzone hidden
    assert screen._guard.busy is False  # released after parse

    screen._on_confirm()
    tk_root.update_idletasks()
    assert screen._pending_rows == []
    assert screen._guard.busy is False
    assert screen.chip.winfo_manager() == ""  # back to dropzone state
    with get_connection(temp_db_path) as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM attendance_records").fetchone()[0]
        assert count == 5
        assert get_setting(conn, "current_month") == "2026-04"
    assert len(toasts) == 1
    assert "5 baris fingerprint berhasil diimpor" in toasts[0]["message"]
    assert "April 2026" in toasts[0]["message"]
    screen.destroy()


def test_double_ingest_guard_noops(
        temp_db_path, monkeypatch, tk_root, synthetic_fingerprint_xls):
    screen = _make_screen(temp_db_path, monkeypatch, tk_root)
    started = []
    # run_bg fake that never completes — the parse stays "in flight"
    monkeypatch.setattr(mod, "run_bg",
                        lambda widget, work, **kw: started.append(work))

    screen._ingest_paths([synthetic_fingerprint_xls])
    assert len(started) == 1
    assert screen._guard.busy is True
    assert screen._browse_btn.cget("state") == "disabled"

    screen._ingest_paths([synthetic_fingerprint_xls])  # double click
    assert len(started) == 1  # no second worker started
    screen.destroy()


def test_pick_file_noops_while_busy(temp_db_path, monkeypatch, tk_root):
    screen = _make_screen(temp_db_path, monkeypatch, tk_root)
    assert screen._guard.acquire() is True
    monkeypatch.setattr(
        mod.filedialog, "askopenfilenames",
        lambda **kw: pytest.fail("file dialog opened while an op runs"),
    )
    screen._on_pick_file()  # returns silently, no dialog
    screen._guard.release()
    screen.destroy()


def test_parse_error_shows_dark_feedback(
        temp_db_path, monkeypatch, tk_root, tmp_path):
    screen = _make_screen(temp_db_path, monkeypatch, tk_root)
    monkeypatch.setattr(mod, "run_bg", _sync_run_bg)
    errors = []
    monkeypatch.setattr(mod.feedback, "show_error",
                        lambda parent, title, msg: errors.append((title, msg)))

    screen._ingest_paths([tmp_path / "hilang.xls"])  # parse will raise
    tk_root.update_idletasks()
    assert len(errors) == 1
    assert errors[0][0] == "Error parsing"
    assert screen._pending_rows == []
    assert screen._guard.busy is False  # released on error
    screen.destroy()


def test_empty_parse_shows_warning_and_keeps_state_clean(
        temp_db_path, monkeypatch, tk_root, synthetic_fingerprint_xls):
    screen = _make_screen(temp_db_path, monkeypatch, tk_root)
    monkeypatch.setattr(mod, "run_bg", _sync_run_bg)
    monkeypatch.setattr(mod, "parse_fingerprint_file", lambda p: [])
    warnings_seen = []
    monkeypatch.setattr(
        mod.feedback, "show_warning",
        lambda parent, title, msg: warnings_seen.append((title, msg)))

    screen._ingest_paths([synthetic_fingerprint_xls])
    tk_root.update_idletasks()
    assert warnings_seen == [(
        "File kosong",
        "Tidak ada baris yang bisa diimpor dari file yang dipilih.",
    )]
    assert screen._pending_rows == []
    assert screen._guard.busy is False
    screen.destroy()


class _StubModal:
    def __init__(self, parent, title="Memproses..."):
        self.title = title
        self.calls = []

    def open(self):
        self.calls.append(("open",))
        return self

    def set_progress(self, pct, status):
        self.calls.append(("set", pct, status))

    def close(self):
        self.calls.append(("close",))


def test_confirm_over_50_rows_drives_progress_modal(
        temp_db_path, monkeypatch, tk_root):
    screen = _make_screen(temp_db_path, monkeypatch, tk_root)
    monkeypatch.setattr(mod, "run_bg", _sync_run_bg)
    monkeypatch.setattr(mod, "show_success_toast", lambda parent, **kw: None)
    created = []

    def stub_factory(parent, title="Memproses..."):
        m = _StubModal(parent, title)
        created.append(m)
        return m

    monkeypatch.setattr(mod, "ProgressModal", stub_factory)
    screen._pending_rows = [
        _fp_row(f"90{e:02d}", f"EMP{e}", f"2026-04-{d:02d}")
        for e in (1, 2) for d in range(1, 31)
    ]  # 60 rows > 50 threshold
    screen._on_confirm()
    tk_root.update_idletasks()

    assert len(created) == 1
    modal = created[0]
    assert modal.title == "Memproses Import"
    assert modal.calls[0] == ("open",)
    assert modal.calls[1] == ("set", 0.0, "Inserting 60 rows...")
    assert ("set", 10 / 60, "Inserting row 10/60...") in modal.calls
    assert modal.calls[-1] == ("close",)
    with get_connection(temp_db_path) as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM attendance_records").fetchone()[0]
        assert count == 60
    screen.destroy()


def test_confirm_under_50_rows_skips_modal(temp_db_path, monkeypatch, tk_root):
    screen = _make_screen(temp_db_path, monkeypatch, tk_root)
    monkeypatch.setattr(mod, "run_bg", _sync_run_bg)
    monkeypatch.setattr(mod, "show_success_toast", lambda parent, **kw: None)
    monkeypatch.setattr(
        mod, "ProgressModal",
        lambda *a, **kw: pytest.fail("modal must not open for <=50 rows"))
    screen._pending_rows = [_fp_row("9001", "BUDI", "2026-04-01")]
    screen._on_confirm()
    tk_root.update_idletasks()
    with get_connection(temp_db_path) as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM attendance_records").fetchone()[0] == 1
    screen.destroy()


def test_confirm_error_closes_modal_shows_error_keeps_pending(
        temp_db_path, monkeypatch, tk_root):
    screen = _make_screen(temp_db_path, monkeypatch, tk_root)
    monkeypatch.setattr(mod, "run_bg", _sync_run_bg)
    errors = []
    monkeypatch.setattr(mod.feedback, "show_error",
                        lambda parent, title, msg: errors.append((title, msg)))

    def boom(conn):
        raise RuntimeError("db meledak")

    monkeypatch.setattr(mod, "restamp_holidays", boom)
    rows = [_fp_row("9001", "BUDI", "2026-04-01")]
    screen._pending_rows = rows
    screen._on_confirm()
    tk_root.update_idletasks()
    assert errors == [("Error import", "db meledak")]
    assert screen._pending_rows == rows  # kept — user can retry
    assert screen._guard.busy is False
    with get_connection(temp_db_path) as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM attendance_records").fetchone()[0] == 0
    screen.destroy()


# ── componentized banner / chip / history ──

def test_banner_warn_state_on_month_mismatch(temp_db_path, monkeypatch, tk_root):
    from src.ui.theme import COLOR_INFO_TINT_BG, COLOR_WARN_TINT_BG
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        set_setting(conn, "current_month", "2026-03")
    screen = mod.ImportScreen(tk_root)
    tk_root.update_idletasks()
    assert screen.banner.cget("fg_color") == COLOR_INFO_TINT_BG
    assert screen.banner.text_label.cget("text") == (
        "Bulan aktif saat ini: Maret 2026. "
        "File baru akan auto-detect bulan dan update jika berbeda."
    )

    screen._pending_rows = [_fp_row("9001", "BUDI", "2026-04-01")]
    screen._update_banner()
    assert screen.banner.cget("fg_color") == COLOR_WARN_TINT_BG
    assert screen.banner.text_label.cget("text") == (
        "Bulan aktif akan diubah: Maret 2026 → April 2026 "
        "setelah konfirmasi impor."
    )
    screen.destroy()


def test_chip_content_and_guard_rewire(temp_db_path, monkeypatch, tk_root, tmp_path):
    screen = _make_screen(temp_db_path, monkeypatch, tk_root)
    screen._pending_paths = [tmp_path / "a.xls", tmp_path / "b.xls"]
    screen._show_chip("2 file dipilih", 120, 45)
    tk_root.update_idletasks()
    texts = " ".join(_all_text(screen.chip))
    assert "FILES TERPILIH (2 files)" in texts
    assert "120 KB · diparsing dalam 45 ms" in texts
    assert len(screen.chip.action_buttons) == 3
    # guard tracks the fresh chip buttons + browse after set_content
    assert screen._guard.acquire() is True
    assert screen.chip.action_buttons[2].cget("state") == "disabled"
    assert screen._browse_btn.cget("state") == "disabled"
    screen._guard.release()
    assert screen.chip.action_buttons[2].cget("state") == "normal"
    screen.destroy()


def test_history_renders_via_component(
        temp_db_path, monkeypatch, tk_root, synthetic_fingerprint_xls):
    screen = _make_screen(temp_db_path, monkeypatch, tk_root)
    assert "(belum ada riwayat impor)" in " ".join(_all_text(screen.history))

    rows = mod.parse_import_files([synthetic_fingerprint_xls])["rows"]
    mod.run_import_confirm(temp_db_path, rows)
    screen._render_history()
    tk_root.update_idletasks()
    texts = " ".join(_all_text(screen.history))
    assert "fingerprint_w1.xlsx" in texts
    assert "✓ 2 emp" in texts  # BUDI + ANI
    assert "(belum ada riwayat impor)" not in texts
    screen.destroy()
