"""Analisa 2 bug laporan klien (tanpa fix):
(1) lembur dipilih banyak -> diterima -> 'hilang'
(2) setelah 14 Sep semua kedatangan masih terhitung telat
"""
import sys
import tempfile
from collections import Counter
from pathlib import Path

sys.path.insert(0, r"D:\Gawe\Project X\HR App")

from src.core.attendance_calc import recompute
from src.core.heatmap import build_heatmap_context
from src.core.insights import terlambat_ranking
from src.db.attendance import upsert_attendance
from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.overtime import apply_status
from src.db.schedule import schedule_for
from src.db.schema import init_db
from src.db.settings import set_setting

print("=" * 72)
print("BUG 2 - 'Setelah 14 Sep semua kedatangan masih terhitung telat'")
print("=" * 72)

DB = Path(tempfile.gettempdir()) / "v26_analyze_bug2.db"
if DB.exists():
    DB.unlink()
init_db(DB)   # fresh install (klien): jadwal 09.00-17.00 sejak awal

with get_connection(DB) as conn:
    eid = upsert_employee(conn, no_staff="1", nama="AGUS")
    # Tiga baris dengan isi kolom "Terlambat" dari file fingerprint yang
    # asal perhitungannya berbeda-beda (tanggal dipisah agar tidak saling
    # menimpa):
    cases = [
        ("A export mesin MASIH 08.00 (08:55 -> Terlambat=55)",
         "2026-09-15", "08:55", 55),
        ("B export mesin 09.00 (09:05 -> Terlambat=5)",
         "2026-09-16", "09:05", 5),
        ("C telat beneran (09:20 -> Terlambat=20)",
         "2026-09-17", "09:20", 20),
    ]
    for _, tgl, masuk, telat in cases:
        upsert_attendance(
            conn, employee_id=eid, tanggal=tgl, hari=None,
            tipe="Hari Kerja", jadwal=None, masuk=masuk, keluar="17:05",
            kerja_jam=8.0, lembur_jam=0.0, terlambat_menit=telat,
            has_issue=0, imported_from="fp.xls")

    sched = schedule_for(conn, "2026-09-15")
    ctx = build_heatmap_context(conn, "2026-09", exclude_outliers=False)
    cells = ctx["employees"][0]["cells"]
    ranking = terlambat_ranking(conn, "2026-09-01", "2026-09-30")

print(f"jadwal berlaku 15 Sep  : {sched[0]} - {sched[1]}")
for _, tgl, masuk, telat in cases:
    d = int(tgl[-2:])
    print(f"  {tgl} masuk {masuk} (Terlambat file={telat:>2}) "
          f"-> heatmap={cells[d]['status']!r} telat={cells[d]['telat']}")
print(f"dashboard total telat  : {ranking[0]['total_terlambat']} mnt")
print()
print("Hitung ulang oleh aplikasi (recompute) dengan jadwal 09.00:")
for label, _, masuk, _ in cases:
    r = recompute(tipe="Hari Kerja", masuk=masuk, keluar="17:05",
                  schedule_start=sched[0], schedule_end=sched[1])
    print(f"  {label:50} -> app = {r['terlambat_menit']} mnt")
print()
print("KESIMPULAN BUG 2:")
print("- Tampilan (heatmap/dashboard/export) memakai angka 'Terlambat' DARI")
print("  FILE FINGERPRINT apa adanya; aplikasi TIDAK menghitung ulang telat")
print("  dari jam kantornya sendiri (kecuali dialog Edit Data).")
print("- Kasus A (mesin fingerprint belum diubah ke 09.00): 08:55 tetap")
print("  dihitung 55 mnt telat -> 'semua kedatangan masih telat'.")
print("- Kasus B (file sudah 09.00): 09:05 = 5 mnt, tidak telat.")
print("=> Penyebab pasti dipastikan dari 1 baris data klien:")
print("   tanggal >= 14 Sep: nilai 'Masuk' vs 'Terlambat' di DB-nya.")

print()
print("=" * 72)
print("BUG 1 - 'dipilih banyak lalu diterima masih hilang'")
print("=" * 72)

import customtkinter as ctk  # noqa: E402

DB2 = Path(tempfile.gettempdir()) / "v26_analyze_bug1.db"
if DB2.exists():
    DB2.unlink()
init_db(DB2)

import src.ui.screens.overtime as screen_mod  # noqa: E402
import src.ui.components.overtime_detail_dialog as dlg_mod  # noqa: E402

screen_mod.DB_PATH = DB2
dlg_mod.DB_PATH = DB2

toasts = []
screen_mod.show_success_toast = (
    lambda *a, **k: toasts.append(k.get("message", "")))
screen_mod.feedback.show_warning = lambda *a, **k: None


def att(conn, eid, tanggal, masuk, keluar):
    upsert_attendance(
        conn, employee_id=eid, tanggal=tanggal, hari=None, tipe="Hari Kerja",
        jadwal=None, masuk=masuk, keluar=keluar, kerja_jam=None,
        lembur_jam=None, terlambat_menit=0, has_issue=0, imported_from="t")


with get_connection(DB2) as conn:
    set_setting(conn, "current_month", "2026-10")
    eid = upsert_employee(conn, no_staff="1", nama="AGUS")
    for d in range(1, 14):
        att(conn, eid, f"2026-10-{d:02d}", "09:00", "19:00")
    for d in range(11, 14):   # 3 baris Diajukan
        apply_status(conn, employee_id=eid, tanggal=f"2026-10-{d:02d}",
                     status="diajukan", detected_minutes=120)

root = ctk.CTk()
root.withdraw()


def snap(s, label):
    c = Counter(r.status for r in s._rows)
    print(f"  {label}: rows={len(s._rows)} status={dict(c)}")
    return c


s = screen_mod.OvertimeScreen(root)
root.update_idletasks()
snap(s, "awal")

print("\nSkenario B1: centang SEMUA (10 Open + 3 Diajukan) -> klik 'Terima'")
for iid in list(s._row_by_iid):
    s._toggle_check(iid)
print(f"  dicentang: {len(s._checked)} baris")
toasts.clear()
s._apply_batch("diterima")
root.update_idletasks()
print(f"  toast: {toasts[-1]!r}")
snap(s, "setelah batch Terima")

print("\nSkenario B2: centang 10 baris OPEN saja -> klik 'Terima'")
s._clear_checks()
for iid, r in s._row_by_iid.items():
    if r.status == "open":
        s._toggle_check(iid)
toasts.clear()
s._apply_batch("diterima")
root.update_idletasks()
print(f"  toast: {toasts[-1]!r}")
snap(s, "setelah batch Terima (Open saja)")
print("  -> baris Open TIDAK hilang dari 'Semua'; tab 'Diterima' tidak")
print("     bertambah => terasa seperti 'hilang'.")

print("\nSkenario B3: siapkan 3 baris Diajukan lagi, centang, klik 'Terima'")
with get_connection(DB2) as conn:
    for d in range(11, 14):
        apply_status(conn, employee_id=eid, tanggal=f"2026-10-{d:02d}",
                     status="diajukan", detected_minutes=120)
s._reload()
root.update_idletasks()
s._clear_checks()
for iid, r in s._row_by_iid.items():
    if r.status == "diajukan":
        s._toggle_check(iid)
print(f"  dicentang: {len(s._checked)} baris diajukan")
toasts.clear()
s._apply_batch("diterima")
root.update_idletasks()
print(f"  toast: {toasts[-1]!r}")
snap(s, "setelah batch Terima (Diajukan)")

s.destroy()
root.destroy()
print()
print("KESIMPULAN BUG 1:")
print("- Aksi massal 'Terima' HANYA berlaku untuk baris ber-status Diajukan.")
print("  Baris Open dilewati (dihitung di toast), bukan dihapus.")
print("- Jika klien mencentang banyak baris Open lalu menekan 'Terima',")
print("  hasilnya 0 berubah + N dilewati; tab 'Diterima' tetap kosong.")
print("  Inilah yang terasa 'hilang' - datanya tidak pernah ditulis.")
print("- Perlu konfirmasi dari klien: baris yang dicentang saat itu")
print("  berstatus Open atau Diajukan?")
