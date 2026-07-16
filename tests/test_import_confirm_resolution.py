import pytest

from src.parsers.fingerprint import FingerprintRow
from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.attendance import save_manual_attendance, get_attendance
from src.db import backup
from src.ui.screens.import_screen import run_import_confirm


def _fp(no_staff, tanggal, **kw):
    base = dict(nama="Budi", no_staff=no_staff, dept="Prod", tanggal=tanggal,
                hari="Rabu", tipe="Hari Kerja", jadwal="", masuk="08:00",
                keluar=None, kerja_jam=None, lembur_jam=None, terlambat_menit=0,
                source_file="f.xls")
    base.update(kw)
    return FingerprintRow(**base)


def _seed_manual(db):
    with get_connection(db) as c:
        eid = upsert_employee(c, no_staff="S1", nama="Budi", dept="Prod")
        save_manual_attendance(
            c, employee_id=eid, tanggal="2026-05-06", hari="Rabu",
            tipe="Hari Kerja", jadwal="", masuk="08:00", keluar="16:05",
            kerja_jam=8.1, lembur_jam=0.1, terlambat_menit=0, has_issue=0)
    return eid


def test_keep_preserves_manual_and_writes_new(tmp_path):
    db = tmp_path / "hr.db"
    init_db(db)
    eid = _seed_manual(db)
    rows = [_fp("S1", "2026-05-06", keluar=None),                    # conflict -> keep
            _fp("S1", "2026-05-07", keluar="16:00", hari="Kamis")]   # new row
    out = run_import_confirm(db, rows, resolution={("S1", "2026-05-06"): "keep"})
    assert out["row_count"] == 2
    with get_connection(db) as c:
        kept = get_attendance(c, employee_id=eid, tanggal="2026-05-06")
        new = get_attendance(c, employee_id=eid, tanggal="2026-05-07")
    assert kept["keluar"] == "16:05"                 # manual preserved
    assert kept["manual_edited_at"] is not None       # still flagged
    assert new is not None and new["keluar"] == "16:00"
    assert any(b["reason"] == "sebelum-import" for b in backup.list_backups(db))


def test_take_overwrites_and_clears_flag(tmp_path):
    db = tmp_path / "hr.db"
    init_db(db)
    eid = _seed_manual(db)
    rows = [_fp("S1", "2026-05-06", keluar="17:00")]
    run_import_confirm(db, rows, resolution={("S1", "2026-05-06"): "take"})
    with get_connection(db) as c:
        row = get_attendance(c, employee_id=eid, tanggal="2026-05-06")
    assert row["keluar"] == "17:00"                  # import won
    assert row["manual_edited_at"] is None            # flag cleared


# ---- conflict dialog smoke ----
@pytest.fixture(scope="module")
def root():
    ctk = pytest.importorskip("customtkinter")
    try:
        r = ctk.CTk()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"no Tk display: {exc}")
    r.withdraw()
    yield r
    try:
        r.destroy()
    except Exception:
        pass


def test_conflict_dialog_default_keep_and_bulk_take(root):
    from src.ui.components.import_conflict_dialog import ImportConflictDialog
    conflicts = [{
        "key": ("S1", "2026-05-06"), "no_staff": "S1", "nama": "Budi",
        "tanggal": "2026-05-06", "hari": "Rabu",
        "manual": {"tipe": "Hari Kerja", "jadwal": "", "masuk": "08:00",
                   "keluar": "16:05", "kerja_jam": 8.1, "lembur_jam": 0.1,
                   "terlambat_menit": 0},
        "incoming": {"tipe": "Hari Kerja", "jadwal": "", "masuk": "08:00",
                     "keluar": None, "kerja_jam": 0.0, "lembur_jam": 0.0,
                     "terlambat_menit": 0},
        "changed": ["keluar", "kerja_jam", "lembur_jam"],
    }]
    dlg = ImportConflictDialog(
        root, conflicts=conflicts, file_label="f.xls",
        non_conflict_count=3, on_resolved=lambda res: None)
    try:
        assert dlg._resolution() == {("S1", "2026-05-06"): "keep"}   # default keep
        dlg._set_all("Pakai import")
        assert dlg._resolution() == {("S1", "2026-05-06"): "take"}
    finally:
        dlg.destroy()
