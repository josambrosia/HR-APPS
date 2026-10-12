"""v26 integration: relasi antar-fitur (jadwal, toleransi, lembur, heatmap,
import, hari libur, cetak, badge) + migrasi DB lama/terinstall.

Berbeda dari tes unit: di sini alur nyata dirangkai — Settings/DB → mesin →
layar/dialog/cetak — untuk menangkap bug lanjutan akibat saling terkait.
"""
import shutil
import sqlite3
from datetime import date
from pathlib import Path

import pytest

from src.core.heatmap import build_heatmap_context
from src.core.overtime import count_pending, month_rows
from src.db.attendance import upsert_attendance
from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.holidays import mark_holidays
from src.db.overtime import apply_status, get_decision
from src.db.schema import init_db
from src.db.settings import get_setting, set_setting
from src.db.tolerance import add_period, list_periods as list_tol_periods


def _legacy_db(p: Path, *, sched=("08.00", "16.00"), tol="12"):
    with sqlite3.connect(p) as conn:
        conn.execute("CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute("INSERT INTO settings VALUES ('schedule_start',?)",
                     (sched[0],))
        conn.execute("INSERT INTO settings VALUES ('schedule_end',?)",
                     (sched[1],))
        conn.execute("INSERT INTO settings VALUES ('late_tolerance_min',?)",
                     (tol,))
        conn.commit()
    init_db(p)


def _att(conn, eid, tanggal, masuk, keluar, *, tipe="Hari Kerja",
         terlambat=0):
    upsert_attendance(
        conn, employee_id=eid, tanggal=tanggal, hari=None, tipe=tipe,
        jadwal=None, masuk=masuk, keluar=keluar, kerja_jam=None,
        lembur_jam=None, terlambat_menit=terlambat, has_issue=0,
        imported_from="t")


# ── 1. Jadwal × lembur × dialog edit data ──────────────────────────────────

def test_schedule_cutover_flows_into_overtime_and_edit_dialog(
        tmp_path, monkeypatch, tk_root):
    p = tmp_path / "i.db"
    _legacy_db(p)
    with get_connection(p) as conn:
        eid = upsert_employee(conn, no_staff="1", nama="Agus")
        _att(conn, eid, "2026-09-10", "08:00", "16:30")   # masih 16.00
        _att(conn, eid, "2026-09-15", "09:00", "19:00")   # sudah 17.00
        rows = month_rows(conn, "2026-09")
        assert [r.tanggal for r in rows] == ["2026-09-15"]
        assert rows[0].minutes == 120                     # 19:00 - 17:00

    import src.ui.components.attendance_edit_dialog as dlg_mod
    monkeypatch.setattr(dlg_mod, "DB_PATH", p)
    d1 = dlg_mod.AttendanceEditDialog(
        tk_root, employee_id=1, nama="Agus", tanggal="2026-09-10",
        on_saved=lambda: None, on_deleted=lambda: None)
    d2 = dlg_mod.AttendanceEditDialog(
        tk_root, employee_id=1, nama="Agus", tanggal="2026-09-15",
        on_saved=lambda: None, on_deleted=lambda: None)
    try:
        assert (d1._sched_start, d1._sched_end) == ("08.00", "16.00")
        assert (d2._sched_start, d2._sched_end) == ("09.00", "17.00")
    finally:
        d1.destroy()
        d2.destroy()


# ── 2. Toleransi × heatmap (bulan melintasi perubahan) ─────────────────────

def test_tolerance_periods_flow_into_heatmap_context(tmp_path):
    p = tmp_path / "i.db"
    init_db(p)
    with get_connection(p) as conn:
        eid = upsert_employee(conn, no_staff="1", nama="Agus")
        for tgl in ("2026-10-05", "2026-10-20"):
            _att(conn, eid, tgl, "08:13", "16:00", terlambat=13)
        add_period(conn, effective_from="2026-10-15", tolerance_min=15)
        ctx = build_heatmap_context(conn, "2026-10", exclude_outliers=False)
    emp = ctx["employees"][0]
    assert emp["cells"][5]["status"] == "sedang"
    assert emp["cells"][20]["status"] == "hadir"
    # baseline ridge memakai toleransi akhir periode
    assert ctx["late_tolerance"] == 15


# ── 3. Keputusan lembur × import ulang × layar × badge × cetak ─────────────

def test_overtime_decisions_survive_reimport_and_flow_to_screen_print(
        tmp_path, monkeypatch, tk_root):
    p = tmp_path / "i.db"
    init_db(p)
    with get_connection(p) as conn:
        set_setting(conn, "current_month", "2026-10")
        a = upsert_employee(conn, no_staff="1", nama="Agus")
        b = upsert_employee(conn, no_staff="2", nama="Budi")
        _att(conn, a, "2026-10-01", "09:00", "19:30")
        _att(conn, b, "2026-10-02", "09:00", "19:00")
        apply_status(conn, employee_id=a, tanggal="2026-10-01",
                     status="diterima", detected_minutes=150,
                     approved_minutes=120)
        # simulasi import fingerprint ulang menimpa baris yang sama
        _att(conn, a, "2026-10-01", "09:00", "19:30")
        _att(conn, b, "2026-10-02", "09:00", "19:00")
        assert count_pending(conn, "2026-10") == 1
        assert get_decision(conn, a, "2026-10-01")["status"] == "diterima"

    import src.ui.screens.overtime as screen_mod
    import src.ui.components.toast as toast_mod
    monkeypatch.setattr(screen_mod, "DB_PATH", p)
    monkeypatch.setattr(screen_mod, "show_success_toast", lambda *a, **k: None)
    monkeypatch.setattr(toast_mod, "show_success_toast", lambda *a, **k: None)
    s = screen_mod.OvertimeScreen(tk_root)
    tk_root.update_idletasks()
    try:
        assert s._kpi_pending._value_label.cget("text") == "1"
        assert s._kpi_approved._value_label.cget("text") == "2j"
        s._filter = "diterima"
        s._render_table()
        assert len(s.tree.get_children()) == 1
    finally:
        s.destroy()

    from src.reports.overtime_print import render_overtime_print_html
    with get_connection(p) as conn:
        html = render_overtime_print_html(conn, "2026-10", mode="accepted")
    assert "Agus" in html and "2j" in html


# ── 4. Keputusan lembur × tanggal ditandai libur ───────────────────────────

def test_decision_survives_holiday_marking_and_reclassifies(tmp_path):
    p = tmp_path / "i.db"
    init_db(p)
    with get_connection(p) as conn:
        eid = upsert_employee(conn, no_staff="1", nama="Agus")
        _att(conn, eid, "2026-10-01", "09:00", "19:30")
        apply_status(conn, employee_id=eid, tanggal="2026-10-01",
                     status="diterima", detected_minutes=150,
                     approved_minutes=150)
        mark_holidays(conn, ["2026-10-01"])
        row = [r for r in month_rows(conn, "2026-10")
               if r.tanggal == "2026-10-01"][0]
        assert row.status == "diterima"
        assert row.is_holiday is True
        assert row.minutes == 630        # libur: penuh keluar - masuk
        assert row.changed is True       # snapshot 150 vs 630 sekarang


# ── 5. Ambang lembur berubah × keputusan lama tetap tampil ─────────────────

def test_threshold_change_keeps_decided_rows_visible(tmp_path):
    p = tmp_path / "i.db"
    init_db(p)
    with get_connection(p) as conn:
        a = upsert_employee(conn, no_staff="1", nama="Agus")
        b = upsert_employee(conn, no_staff="2", nama="Budi")
        _att(conn, a, "2026-10-01", "09:00", "19:00")   # 120
        _att(conn, b, "2026-10-02", "09:00", "19:00")   # 120
        apply_status(conn, employee_id=a, tanggal="2026-10-01",
                     status="diajukan", detected_minutes=120)
        set_setting(conn, "overtime_threshold", "19.30")
        rows = {r.tanggal: r for r in month_rows(conn, "2026-10")}
        assert "2026-10-01" in rows          # keputusan tetap tampil
        assert rows["2026-10-01"].qualifies is False
        assert rows["2026-10-01"].changed is True
        assert "2026-10-02" not in rows      # baris tanpa keputusan hilang


# ── 6. Migrasi DB lama: jadwal + toleransi + idempoten ─────────────────────

def test_legacy_migration_seeds_schedule_and_tolerance(tmp_path):
    p = tmp_path / "i.db"
    _legacy_db(p, sched=("08.30", "16.30"), tol="20")
    with get_connection(p) as conn:
        sched = [tuple(r) for r in conn.execute(
            "SELECT effective_from, start_time, end_time FROM schedule_periods"
        ).fetchall()]
        tol = list_tol_periods(conn)
    assert sched == [("1970-01-01", "08.30", "16.30")]
    assert len(tol) == 1 and tol[0]["tolerance_min"] == 20
    # idempoten
    init_db(p)
    with get_connection(p) as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM schedule_periods").fetchone()[0] == 1
        assert conn.execute(
            "SELECT COUNT(*) FROM tolerance_periods").fetchone()[0] == 1


# ── 7. Keputusan × edit heatmap × resolve Issues ───────────────────────────

def test_decisions_survive_heatmap_edit_and_issue_resolve(tmp_path):
    from src.db.attendance import save_manual_attendance, set_reason
    p = tmp_path / "i.db"
    init_db(p)
    with get_connection(p) as conn:
        a = upsert_employee(conn, no_staff="1", nama="Agus")
        b = upsert_employee(conn, no_staff="2", nama="Budi")
        _att(conn, a, "2026-06-03", "08:10", "18:53")
        _att(conn, b, "2026-06-05", "08:07", "22:36")
        apply_status(conn, employee_id=a, tanggal="2026-06-03",
                     status="tidak_diterima", detected_minutes=173)
        apply_status(conn, employee_id=b, tanggal="2026-06-05",
                     status="diterima", detected_minutes=396,
                     approved_minutes=396)
        # edit manual dari Heatmap
        save_manual_attendance(
            conn, employee_id=a, tanggal="2026-06-03", hari="Rabu",
            tipe="Hari Kerja", jadwal=None, masuk="08:10", keluar="18:53",
            kerja_jam=10.7, lembur_jam=2.7, terlambat_menit=0, has_issue=0)
        # resolve dari Issues
        rid = conn.execute(
            "SELECT id FROM attendance_records "
            "WHERE employee_id=? AND tanggal=?", (b, "2026-06-05")).fetchone()["id"]
        set_reason(conn, attendance_id=rid, category="tugas_lapangan",
                   detail="PT X")
        assert get_decision(conn, a, "2026-06-03")["status"] == "tidak_diterima"
        assert get_decision(conn, b, "2026-06-05")["status"] == "diterima"


# ── 8. Import memindah Bulan Aktif: keputusan tetap ada di bulan lama ──────

def test_import_month_switch_keeps_decisions(tmp_path):
    from src.db.overtime import decision_months
    p = tmp_path / "i.db"
    init_db(p)
    with get_connection(p) as conn:
        eid = upsert_employee(conn, no_staff="1", nama="Agus")
        _att(conn, eid, "2026-06-03", "08:10", "18:53")
        apply_status(conn, employee_id=eid, tanggal="2026-06-03",
                     status="diajukan", detected_minutes=173)
        # efek import file bulan baru (import_screen auto-detect)
        set_setting(conn, "current_month", "2026-07")
        assert month_rows(conn, "2026-07") == []
        assert decision_months(conn) == [{"month": "2026-06", "total": 1}]
        # kembali ke Juni → keputusan muncul lagi
        set_setting(conn, "current_month", "2026-06")
        rows = month_rows(conn, "2026-06")
        assert [r.status for r in rows] == ["diajukan"]


# ── 9. Migrasi pada salinan DB terinstall (data nyata user) ────────────────

INSTALLED_DB = Path.home() / "AppData/Local/Programs/HR-Absensi/data/hr.db"


@pytest.mark.skipif(not INSTALLED_DB.exists(),
                    reason="DB terinstall tidak ada di mesin ini")
def test_migration_on_installed_db_copy(tmp_path):
    copy = tmp_path / "installed.db"
    shutil.copy2(INSTALLED_DB, copy)
    before_rows = None
    with sqlite3.connect(copy) as conn:
        before_rows = conn.execute(
            "SELECT COUNT(*) FROM attendance_records").fetchone()[0]
    init_db(copy)   # hanya di salinan
    with get_connection(copy) as conn:
        tol = list_tol_periods(conn)
        assert len(tol) == 1
        assert tol[0]["effective_from"] == "1970-01-01"
        # nilai toleransi lama dipertahankan (di DB ini 12)
        assert tol[0]["tolerance_min"] == 12
        # data absensi tidak tersentuh
        assert conn.execute(
            "SELECT COUNT(*) FROM attendance_records").fetchone()[0] == before_rows
        # jadwal tetap 2 periode (08-16 lalu 09-17) dan keputusan lembur utuh
        assert conn.execute(
            "SELECT COUNT(*) FROM schedule_periods").fetchone()[0] == 2
        assert conn.execute(
            "SELECT COUNT(*) FROM overtime_decisions").fetchone()[0] >= 2
