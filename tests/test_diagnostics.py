import json
import sqlite3
import zipfile
from datetime import datetime

from src import config
from src.core.diagnostics import build_summary, write_diagnostic_zip
from src.db.attendance import upsert_attendance
from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.overtime import apply_status
from src.db.schema import init_db
from src.db.settings import set_setting


def _seed(p):
    init_db(p)
    with get_connection(p) as conn:
        set_setting(conn, "current_month", "2026-10")
        eid = upsert_employee(conn, no_staff="1", nama="Agus")
        upsert_attendance(
            conn, employee_id=eid, tanggal="2026-09-15", hari=None,
            tipe="Hari Kerja", jadwal=None, masuk="08:55", keluar="17:05",
            kerja_jam=8.0, lembur_jam=0.0, terlambat_menit=55,
            has_issue=0, imported_from="fp.xls")
        upsert_attendance(
            conn, employee_id=eid, tanggal="2026-10-01", hari=None,
            tipe="Hari Kerja", jadwal=None, masuk="09:00", keluar="19:30",
            kerja_jam=None, lembur_jam=None, terlambat_menit=0,
            has_issue=0, imported_from="fp.xls")
        apply_status(conn, employee_id=eid, tanggal="2026-10-01",
                     status="diajukan", detected_minutes=150)
    return eid


def test_write_diagnostic_zip(tmp_path):
    p = tmp_path / "hr.db"
    _seed(p)
    out = tmp_path / "out"
    zpath = write_diagnostic_zip(p, out, now=datetime(2026, 10, 15, 10, 0, 0))
    assert zpath.exists()
    assert zpath.name == "hr-diagnostik-20261015-100000.zip"
    with zipfile.ZipFile(zpath) as z:
        names = set(z.namelist())
        assert {"hr.db", "summary.json", "samples_setelah_cutoff.csv",
                "keputusan_lembur.csv"} <= names
        summary = json.loads(z.read("summary.json"))
        assert summary["app_version"] == config.APP_VERSION
        assert summary["counts"]["attendance_rows"] == 2
        assert summary["counts"]["overtime_decisions"] == 1
        assert summary["counts"]["attendance_per_month"] == {
            "2026-09": 1, "2026-10": 1}
        samples = z.read("samples_setelah_cutoff.csv").decode()
        assert "08:55" in samples and "55" in samples
        dec = z.read("keputusan_lembur.csv").decode()
        assert "diajukan" in dec and "Agus" in dec


def test_summary_tolerates_missing_v26_tables(tmp_path):
    """DB lama tanpa tabel v26 tetap bisa diekspor (query di-guard)."""
    p = tmp_path / "old.db"
    with sqlite3.connect(p) as conn:
        conn.executescript(
            "CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT);"
            "CREATE TABLE employees (id INTEGER PRIMARY KEY, no_staff TEXT, "
            "nama TEXT, dept TEXT);"
            "CREATE TABLE attendance_records (employee_id INTEGER, "
            "tanggal TEXT, masuk TEXT, keluar TEXT, terlambat_menit INTEGER, "
            "tipe TEXT, reason_category TEXT, imported_from TEXT);"
        )
        conn.commit()
    conn = sqlite3.connect(p)
    conn.row_factory = sqlite3.Row
    try:
        summary = build_summary(conn)
    finally:
        conn.close()
    assert summary["counts"]["overtime_decisions"] is None
    assert summary["schedule_periods"] == []
    assert summary["tolerance_periods"] == []
