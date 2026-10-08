"""v26: dialog detail + verifikasi lembur."""
from src.core.overtime import month_rows
from src.db.attendance import upsert_attendance
from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.overtime import apply_status, get_decision
from src.db.schema import init_db


def _seed(p):
    init_db(p)
    with get_connection(p) as conn:
        a = upsert_employee(conn, no_staff="1", nama="Agus", dept="Ops")
        upsert_attendance(
            conn, employee_id=a, tanggal="2026-10-01", hari=None,
            tipe="Hari Kerja", jadwal=None, masuk="09:00", keluar="19:30",
            kerja_jam=None, lembur_jam=None, terlambat_menit=0,
            has_issue=0, imported_from="t")
    return a


def _row(p, status_filter="open"):
    with get_connection(p) as conn:
        rows = month_rows(conn, "2026-10")
    return [r for r in rows if r.status == status_filter][0]


def test_open_dialog_ajukan(tmp_path, monkeypatch, tk_root):
    import src.ui.components.overtime_detail_dialog as mod
    p = tmp_path / "o.db"
    _seed(p)
    monkeypatch.setattr(mod, "DB_PATH", p)
    saved = []
    dlg = mod.OvertimeDetailDialog(tk_root, _row(p, "open"),
                                   on_saved=lambda: saved.append(1))
    try:
        dlg._apply("diajukan")
    finally:
        if dlg.winfo_exists():
            dlg.destroy()
    assert saved == [1]
    with get_connection(p) as conn:
        d = get_decision(conn, 1, "2026-10-01")
    assert d["status"] == "diajukan"
    assert d["detected_minutes_at_decision"] == 150


def test_diterima_rejects_approved_over_detected(tmp_path, monkeypatch, tk_root):
    import src.ui.components.overtime_detail_dialog as mod
    p = tmp_path / "o.db"
    _seed(p)
    with get_connection(p) as conn:
        apply_status(conn, employee_id=1, tanggal="2026-10-01",
                     status="diajukan", detected_minutes=150)
    monkeypatch.setattr(mod, "DB_PATH", p)
    warnings = []
    monkeypatch.setattr(mod.feedback, "show_warning",
                        lambda *a, **k: warnings.append(a))
    monkeypatch.setattr(mod.feedback, "ask_yes_no", lambda *a, **k: True)
    dlg = mod.OvertimeDetailDialog(tk_root, _row(p, "diajukan"),
                                   on_saved=lambda: None)
    try:
        dlg._ap_jam.delete(0, "end")
        dlg._ap_jam.insert(0, "9")
        dlg._ap_menit.delete(0, "end")
        dlg._ap_menit.insert(0, "0")
        dlg._apply("diterima")
        assert warnings
    finally:
        if dlg.winfo_exists():
            dlg.destroy()
    with get_connection(p) as conn:
        d = get_decision(conn, 1, "2026-10-01")
    assert d["status"] == "diajukan"


def test_diterima_saves_partial_and_note(tmp_path, monkeypatch, tk_root):
    import src.ui.components.overtime_detail_dialog as mod
    p = tmp_path / "o.db"
    _seed(p)
    with get_connection(p) as conn:
        apply_status(conn, employee_id=1, tanggal="2026-10-01",
                     status="diajukan", detected_minutes=150)
    monkeypatch.setattr(mod, "DB_PATH", p)
    monkeypatch.setattr(mod.feedback, "ask_yes_no", lambda *a, **k: True)
    monkeypatch.setattr(mod.feedback, "show_warning", lambda *a, **k: None)
    dlg = mod.OvertimeDetailDialog(tk_root, _row(p, "diajukan"),
                                   on_saved=lambda: None)
    try:
        dlg._ap_jam.delete(0, "end")
        dlg._ap_jam.insert(0, "1")
        dlg._ap_menit.delete(0, "end")
        dlg._ap_menit.insert(0, "30")
        dlg._note.insert("1.0", "disetujui 1,5 jam")
        dlg._apply("diterima")
    finally:
        if dlg.winfo_exists():
            dlg.destroy()
    with get_connection(p) as conn:
        d = get_decision(conn, 1, "2026-10-01")
    assert d["status"] == "diterima"
    assert d["approved_minutes"] == 90
    assert d["note"] == "disetujui 1,5 jam"


def test_revert_to_open_removes_decision(tmp_path, monkeypatch, tk_root):
    import src.ui.components.overtime_detail_dialog as mod
    p = tmp_path / "o.db"
    _seed(p)
    with get_connection(p) as conn:
        apply_status(conn, employee_id=1, tanggal="2026-10-01",
                     status="diajukan", detected_minutes=150)
    monkeypatch.setattr(mod, "DB_PATH", p)
    monkeypatch.setattr(mod.feedback, "ask_yes_no", lambda *a, **k: True)
    dlg = mod.OvertimeDetailDialog(tk_root, _row(p, "diajukan"),
                                   on_saved=lambda: None)
    try:
        dlg._apply("open")
    finally:
        if dlg.winfo_exists():
            dlg.destroy()
    with get_connection(p) as conn:
        assert get_decision(conn, 1, "2026-10-01") is None


def test_dialog_handles_missing_data_row(tmp_path, monkeypatch, tk_root):
    """Keputusan yatim tetap bisa diverifikasi dari dialognya."""
    import src.ui.components.overtime_detail_dialog as mod
    from src.db.attendance import delete_attendance
    p = tmp_path / "o.db"
    _seed(p)
    with get_connection(p) as conn:
        apply_status(conn, employee_id=1, tanggal="2026-10-01",
                     status="diajukan", detected_minutes=150)
        delete_attendance(conn, employee_id=1, tanggal="2026-10-01")
    monkeypatch.setattr(mod, "DB_PATH", p)
    monkeypatch.setattr(mod.feedback, "ask_yes_no", lambda *a, **k: True)
    monkeypatch.setattr(mod.feedback, "show_warning", lambda *a, **k: None)
    row = _row(p, "diajukan")
    assert row.missing_data is True
    dlg = mod.OvertimeDetailDialog(tk_root, row, on_saved=lambda: None)
    try:
        dlg._apply("tidak_diterima")
    finally:
        if dlg.winfo_exists():
            dlg.destroy()
    with get_connection(p) as conn:
        d = get_decision(conn, 1, "2026-10-01")
    assert d["status"] == "tidak_diterima"
