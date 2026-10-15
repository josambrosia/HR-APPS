"""Ekspor paket diagnostik untuk dukungan (v26.0.1).

Membuat SATU file zip berisi salinan database + ringkasan + contoh baris,
supaya masalah di komputer klien bisa dianalisa tanpa akses langsung:

- ``hr.db``                      salinan penuh database (read-only copy)
- ``summary.json``               versi aplikasi, jadwal, toleransi, hitungan
- ``samples_setelah_cutoff.csv`` baris absensi tanggal >= 2026-09-14 dengan
                                 pembanding nilai tersimpan (db) vs hitungan
                                 aplikasi (app) untuk telat & lembur
- ``keputusan_lembur.csv``       seluruh keputusan lembur + timestamp
"""
import csv
import io
import json
import sqlite3
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from src.config import APP_BUILD_DATE, APP_VERSION, SCHEDULE_CUTOVER_DATE
from src.core.attendance_calc import recompute
from src.db.schedule import schedule_for

_SETTING_KEYS = (
    "current_month", "schedule_start", "schedule_end", "overtime_threshold",
    "late_tolerance_min", "severe_lateness_threshold_min",
    "coaching_threshold_per_day", "lupa_absen_datang_penalty_min",
    "hr_officer_name",
)


def _try_rows(conn, sql, params=()):
    try:
        return conn.execute(sql, params).fetchall()
    except sqlite3.OperationalError:
        return []   # tabel belum ada (DB lama) — tetap ekspor sisanya


def build_summary(conn: sqlite3.Connection) -> dict:
    def one(sql, params=()):
        row = conn.execute(sql, params).fetchone()
        return row[0] if row else None

    months = {r["m"]: r["n"] for r in _try_rows(
        conn,
        "SELECT substr(tanggal,1,7) m, COUNT(*) n FROM attendance_records "
        "GROUP BY m ORDER BY m")}
    decisions = {f"{r['m']}:{r['status']}": r["n"] for r in _try_rows(
        conn,
        "SELECT substr(tanggal,1,7) m, status, COUNT(*) n "
        "FROM overtime_decisions GROUP BY m, status")}
    ot_count_rows = _try_rows(conn, "SELECT COUNT(*) c FROM overtime_decisions")
    settings = {}
    for k in _SETTING_KEYS:
        row = conn.execute(
            "SELECT value FROM settings WHERE key = ?", (k,)).fetchone()
        settings[k] = row["value"] if row else None
    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "app_version": APP_VERSION,
        "app_build_date": APP_BUILD_DATE,
        "cutoff_tanggal": SCHEDULE_CUTOVER_DATE,
        "counts": {
            "employees": one("SELECT COUNT(*) FROM employees"),
            "attendance_rows": one("SELECT COUNT(*) FROM attendance_records"),
            "attendance_per_month": months,
            "overtime_decisions": (ot_count_rows[0]["c"]
                                   if ot_count_rows else None),
            "overtime_decisions_per_month_status": decisions,
        },
        "schedule_periods": [dict(r) for r in _try_rows(
            conn,
            "SELECT effective_from, start_time, end_time FROM schedule_periods "
            "ORDER BY effective_from")],
        "tolerance_periods": [dict(r) for r in _try_rows(
            conn,
            "SELECT effective_from, tolerance_min FROM tolerance_periods "
            "ORDER BY effective_from")],
        "settings": settings,
        "last_import_at": (_try_rows(
            conn, "SELECT MAX(imported_at) mx FROM attendance_records")
            or [{"mx": None}])[0]["mx"],
    }


def _samples_rows(conn: sqlite3.Connection) -> list[dict]:
    """Baris setelah cutoff + pembanding nilai tersimpan vs hitungan aplikasi.

    ``terlambat_db``/``lembur_db`` = nilai tersimpan di database (hasil
    import/recompute); ``terlambat_app``/``lembur_app`` = hitungan aplikasi
    saat ini dari jam absensi + jadwal tanggal (v26.0.2). Keduanya harus
    sama kecuali baris yang pernah diedit manual.
    """
    raw = [dict(r) for r in _try_rows(
        conn,
        """
        SELECT ar.tanggal, e.nama, e.dept, ar.masuk, ar.keluar,
               ar.tipe, ar.reason_category, ar.imported_from,
               ar.terlambat_menit AS terlambat_db,
               ar.lembur_jam AS lembur_db
          FROM attendance_records ar
          JOIN employees e ON e.id = ar.employee_id
         WHERE ar.tanggal >= ?
         ORDER BY ar.tanggal, e.nama
         LIMIT 2000
        """,
        (SCHEDULE_CUTOVER_DATE,))]
    sched_cache: dict[str, tuple[str, str]] = {}
    out = []
    for r in raw:
        tgl = r["tanggal"]
        if tgl not in sched_cache:
            sched_cache[tgl] = schedule_for(conn, tgl)
        sched_start, sched_end = sched_cache[tgl]
        calc = recompute(tipe=r["tipe"], masuk=r["masuk"], keluar=r["keluar"],
                         schedule_start=sched_start, schedule_end=sched_end)
        out.append({**r,
                    "terlambat_app": calc["terlambat_menit"],
                    "lembur_app": calc["lembur_jam"]})
    return out


def _decision_rows(conn: sqlite3.Connection) -> list[dict]:
    return [dict(r) for r in _try_rows(
        conn,
        """
        SELECT od.tanggal, e.nama, od.status, od.approved_minutes,
               od.detected_minutes_at_decision, od.note,
               od.submitted_at, od.decided_at, od.updated_at
          FROM overtime_decisions od
          JOIN employees e ON e.id = od.employee_id
         ORDER BY od.tanggal, e.nama
        """)]


def _to_csv(rows: list[dict]) -> str:
    if not rows:
        return ""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


def write_diagnostic_zip(db_path, out_dir, now=None) -> Path:
    """Tulis paket diagnostik zip ke ``out_dir``; return path zip-nya."""
    db_path = Path(db_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    now = now or datetime.now()
    dest = out_dir / f"hr-diagnostik-{now:%Y%m%d-%H%M%S}.zip"

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        summary = build_summary(conn)
        samples = _samples_rows(conn)
        decisions = _decision_rows(conn)
    finally:
        conn.close()

    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(db_path, "hr.db")
        z.writestr("summary.json",
                   json.dumps(summary, indent=2, ensure_ascii=False))
        z.writestr("samples_setelah_cutoff.csv", _to_csv(samples))
        z.writestr("keputusan_lembur.csv", _to_csv(decisions))
    return dest
