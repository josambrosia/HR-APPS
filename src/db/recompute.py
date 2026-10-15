"""Backfill hasil hitung baru (v26.0.2) untuk data yang sudah ada.

Sejak v26.0.2 aplikasi menghitung sendiri ``terlambat_menit`` &
``lembur_jam`` dari jam absensi + jadwal per tanggal. Data yang diimpor
sebelum versi ini masih membawa angka mesin fingerprint, jadi dihitung
ulang SEKALI saat database pertama kali dibuka dengan versi baru
(flag settings ``recompute_app_v262``). Baris yang pernah diedit manual
(``manual_edited_at``) tidak pernah ditimpa; ``kerja_jam`` dan
``has_issue`` tidak disentuh.
"""
import sqlite3
from datetime import UTC, datetime

from src.core.attendance_calc import recompute
from src.db.schedule import schedule_for
from src.db.settings import set_setting

FLAG_KEY = "recompute_app_v262"


def recompute_all_records(conn: sqlite3.Connection) -> int:
    """Hitung ulang terlambat & lembur seluruh baris non-manual.

    Idempoten lewat flag settings (dipasang setelah selesai). Return
    jumlah baris yang nilainya berubah. Wajib dipanggil dengan koneksi
    row_factory (butuh akses per-kolom).
    """
    done = conn.execute(
        "SELECT 1 FROM settings WHERE key = ?", (FLAG_KEY,)).fetchone()
    if done is not None:
        return 0

    # Skema sangat lama (pra-kolom tipe/lembur) tidak bisa dihitung ulang —
    # lewati tanpa memasang flag supaya migrasi skema berikutnya tetap bisa.
    cols = {r[1] for r in conn.execute(
        "PRAGMA table_info(attendance_records)")}
    required = {"tanggal", "tipe", "masuk", "keluar",
                "terlambat_menit", "lembur_jam", "manual_edited_at"}
    if not required <= cols:
        return 0

    rows = conn.execute(
        "SELECT id, tanggal, tipe, masuk, keluar, "
        "       terlambat_menit, lembur_jam "
        "  FROM attendance_records WHERE manual_edited_at IS NULL"
    ).fetchall()
    sched_cache: dict[str, tuple[str, str]] = {}
    updates = []
    for r in rows:
        tgl = r["tanggal"]
        if tgl not in sched_cache:
            sched_cache[tgl] = schedule_for(conn, tgl)
        sched_start, sched_end = sched_cache[tgl]
        calc = recompute(tipe=r["tipe"], masuk=r["masuk"], keluar=r["keluar"],
                         schedule_start=sched_start, schedule_end=sched_end)
        if (calc["terlambat_menit"] != r["terlambat_menit"]
                or calc["lembur_jam"] != r["lembur_jam"]):
            updates.append(
                (calc["terlambat_menit"], calc["lembur_jam"], r["id"]))
    conn.executemany(
        "UPDATE attendance_records SET terlambat_menit = ?, lembur_jam = ? "
        "WHERE id = ?",
        updates,
    )
    set_setting(conn, FLAG_KEY, datetime.now(UTC).isoformat(timespec="seconds"))
    return len(updates)
