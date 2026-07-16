"""Smoke: the attendance edit dialog builds, previews live, and saves.

Headless (root withdrawn, no mainloop). One shared CTk root for the module
(creating multiple CTk roots per process is flaky). Skips if no Tk display.
"""
import pytest


@pytest.fixture(scope="module")
def root():
    ctk = pytest.importorskip("customtkinter")
    try:
        r = ctk.CTk()
    except Exception as exc:  # pragma: no cover - headless CI
        pytest.skip(f"no Tk display: {exc}")
    r.withdraw()
    yield r
    try:
        r.destroy()
    except Exception:
        pass


def _setup(tmp_path, monkeypatch):
    from src.ui.components import attendance_edit_dialog as D
    from src.db.schema import init_db
    from src.db.connection import get_connection
    from src.db.employees import upsert_employee
    dbp = tmp_path / "hr.db"
    init_db(dbp)
    with get_connection(dbp) as c:
        eid = upsert_employee(c, no_staff="S1", nama="Budi")
    monkeypatch.setattr(D, "DB_PATH", dbp)
    return D, dbp, eid


def test_preview_matches_recompute(tmp_path, monkeypatch, root):
    from src.core.attendance_calc import recompute
    D, dbp, eid = _setup(tmp_path, monkeypatch)
    dlg = D.AttendanceEditDialog(
        root, employee_id=eid, nama="Budi", tanggal="2026-05-06",
        on_saved=lambda: None, on_deleted=lambda: None)
    try:
        dlg._masuk.insert(0, "08:20")
        dlg._keluar.insert(0, "16:30")
        got = dlg._recompute_preview()
        assert got == recompute(tipe="Hari Kerja", masuk="08:20", keluar="16:30",
                                schedule_start="08.00", schedule_end="16.00")
    finally:
        dlg.destroy()


def test_save_writes_row_with_flag(tmp_path, monkeypatch, root):
    from src.db.connection import get_connection
    from src.db.attendance import get_attendance
    D, dbp, eid = _setup(tmp_path, monkeypatch)
    saved = []
    dlg = D.AttendanceEditDialog(
        root, employee_id=eid, nama="Budi", tanggal="2026-05-06",
        on_saved=lambda: saved.append(1), on_deleted=lambda: None)
    dlg._masuk.insert(0, "08:00")
    dlg._keluar.insert(0, "16:05")
    dlg._save()          # destroys the dialog on success
    assert saved == [1]
    with get_connection(dbp) as c:
        row = get_attendance(c, employee_id=eid, tanggal="2026-05-06")
    assert row["keluar"] == "16:05"
    assert row["has_issue"] == 0
    assert row["manual_edited_at"] is not None
