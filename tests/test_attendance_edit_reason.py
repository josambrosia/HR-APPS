"""Seksi 'Alasan / Keterangan' di editor absensi: opsi kontekstual + simpan."""
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


def _dlg(D, root, eid, tanggal="2026-07-06"):
    return D.AttendanceEditDialog(
        root, employee_id=eid, nama="Budi", tanggal=tanggal,
        on_saved=lambda: None, on_deleted=lambda: None)


def test_late_reasons_hidden_when_not_late(tmp_path, monkeypatch, root):
    from src.core.reason_mapper import REASON_LABELS
    D, _dbp, eid = _setup(tmp_path, monkeypatch)
    dlg = _dlg(D, root, eid)
    try:
        dlg._masuk.insert(0, "08:00")   # tepat waktu
        dlg._keluar.insert(0, "16:00")
        dlg._recompute_preview()
        values = dlg._reason_menu.cget("values")
        assert REASON_LABELS["tugas_paparan"] in values
        assert REASON_LABELS["izin_sakit"] in values
        assert REASON_LABELS["terlambat_kerja"] not in values
        assert REASON_LABELS["terlambat_lain"] not in values
    finally:
        dlg.destroy()


def test_late_reasons_appear_when_late(tmp_path, monkeypatch, root):
    from src.core.reason_mapper import REASON_LABELS
    D, _dbp, eid = _setup(tmp_path, monkeypatch)
    dlg = _dlg(D, root, eid)
    try:
        dlg._masuk.insert(0, "08:20")   # telat 20 mnt (di bawah ambang severe)
        dlg._keluar.insert(0, "16:00")
        dlg._recompute_preview()
        values = dlg._reason_menu.cget("values")
        assert REASON_LABELS["terlambat_kerja"] in values
        assert REASON_LABELS["terlambat_lain"] in values
    finally:
        dlg.destroy()


def test_lupa_absen_and_libur_never_offered(tmp_path, monkeypatch, root):
    from src.core.reason_mapper import REASON_LABELS
    D, _dbp, eid = _setup(tmp_path, monkeypatch)
    dlg = _dlg(D, root, eid)
    try:
        dlg._masuk.insert(0, "09:30")
        dlg._recompute_preview()
        values = dlg._reason_menu.cget("values")
        for cat in ("lupa_absen_datang", "lupa_absen_pulang", "libur", "na"):
            assert REASON_LABELS[cat] not in values
    finally:
        dlg.destroy()


def test_detail_field_visible_only_for_categories_needing_detail(tmp_path, monkeypatch, root):
    from src.core.reason_mapper import REASON_LABELS
    D, _dbp, eid = _setup(tmp_path, monkeypatch)
    dlg = _dlg(D, root, eid)
    try:
        dlg._reason_var.set(REASON_LABELS["tugas_paparan"])
        dlg._on_reason_change()
        assert dlg._detail.winfo_manager() != ""      # tampil
        dlg._reason_var.set(REASON_LABELS["cuti"])
        dlg._on_reason_change()
        assert dlg._detail.winfo_manager() == ""      # sembunyi
    finally:
        dlg.destroy()


def test_save_writes_reason_and_detail(tmp_path, monkeypatch, root):
    from src.core.reason_mapper import REASON_LABELS
    from src.db.connection import get_connection
    from src.db.attendance import get_attendance
    D, dbp, eid = _setup(tmp_path, monkeypatch)
    dlg = _dlg(D, root, eid)
    dlg._masuk.insert(0, "08:00")
    dlg._keluar.insert(0, "16:00")
    dlg._recompute_preview()
    dlg._reason_var.set(REASON_LABELS["tugas_paparan"])
    dlg._on_reason_change()
    dlg._detail.insert(0, "Kantor Pusat")
    dlg._save()
    with get_connection(dbp) as c:
        row = get_attendance(c, employee_id=eid, tanggal="2026-07-06")
    assert row["reason_category"] == "tugas_paparan"
    assert row["reason_detail"] == "Kantor Pusat"
    assert row["resolved_at"] is not None
    assert row["has_issue"] == 0          # hari bersih tetap bukan issue


def test_clearing_reason_unresolves_row(tmp_path, monkeypatch, root):
    from src.db.connection import get_connection
    from src.db.attendance import get_attendance, set_reason, save_manual_attendance
    D, dbp, eid = _setup(tmp_path, monkeypatch)
    # baris sudah punya alasan sebelumnya
    with get_connection(dbp) as c:
        save_manual_attendance(
            c, employee_id=eid, tanggal="2026-07-07", hari="Selasa",
            tipe="Hari Kerja", jadwal=None, masuk="08:00", keluar="16:00",
            kerja_jam=8.0, lembur_jam=0.0, terlambat_menit=0, has_issue=0)
        rid = c.execute("SELECT id FROM attendance_records WHERE employee_id=? AND tanggal=?",
                        (eid, "2026-07-07")).fetchone()["id"]
        set_reason(c, attendance_id=rid, category="tugas_lapangan", detail="Site A")
    dlg = _dlg(D, root, eid, tanggal="2026-07-07")
    dlg._reason_var.set(D.NO_REASON)
    dlg._on_reason_change()
    dlg._save()
    with get_connection(dbp) as c:
        row = get_attendance(c, employee_id=eid, tanggal="2026-07-07")
    assert row["reason_category"] is None
    assert row["reason_detail"] is None
    assert row["resolved_at"] is None


def test_existing_reason_preloaded(tmp_path, monkeypatch, root):
    from src.core.reason_mapper import REASON_LABELS
    from src.db.connection import get_connection
    from src.db.attendance import save_manual_attendance, set_reason
    D, dbp, eid = _setup(tmp_path, monkeypatch)
    with get_connection(dbp) as c:
        save_manual_attendance(
            c, employee_id=eid, tanggal="2026-07-08", hari="Rabu",
            tipe="Hari Kerja", jadwal=None, masuk="08:00", keluar="16:00",
            kerja_jam=8.0, lembur_jam=0.0, terlambat_menit=0, has_issue=0)
        rid = c.execute("SELECT id FROM attendance_records WHERE employee_id=? AND tanggal=?",
                        (eid, "2026-07-08")).fetchone()["id"]
        set_reason(c, attendance_id=rid, category="tugas_lapangan", detail="Site B")
    dlg = _dlg(D, root, eid, tanggal="2026-07-08")
    try:
        assert dlg._reason_var.get() == REASON_LABELS["tugas_lapangan"]
        assert dlg._detail.get() == "Site B"
    finally:
        dlg.destroy()
