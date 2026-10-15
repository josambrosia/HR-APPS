"""Matriks replikasi dummy v26: kapan keputusan lembur 'hilang'?

Menguji alur nyata satu per satu dengan data dummy + layar asli.
"""
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, r"D:\Gawe\Project X\HR App")

import customtkinter as ctk

from src.db.attendance import upsert_attendance, save_manual_attendance, set_reason
from src.db.backup import create_backup, restore_backup
from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.holidays import mark_holidays
from src.db.overtime import apply_status, get_decision
from src.db.schema import init_db
from src.db.settings import set_setting

DB = Path(tempfile.gettempdir()) / "v26_matrix.db"
if DB.exists():
    DB.unlink()
init_db(DB)

import src.ui.screens.overtime as screen_mod
import src.ui.components.overtime_detail_dialog as dlg_mod
import src.ui.components.toast as toast_mod

screen_mod.DB_PATH = DB
dlg_mod.DB_PATH = DB
dlg_mod.feedback.ask_yes_no = lambda *a, **k: True
dlg_mod.feedback.show_warning = lambda *a, **k: None
screen_mod.feedback.show_warning = lambda *a, **k: None
toast_mod.show_success_toast = lambda *a, **k: None
screen_mod.show_success_toast = lambda *a, **k: None


def att(conn, eid, tanggal, masuk, keluar):
    upsert_attendance(
        conn, employee_id=eid, tanggal=tanggal, hari=None, tipe="Hari Kerja",
        jadwal=None, masuk=masuk, keluar=keluar, kerja_jam=None,
        lembur_jam=None, terlambat_menit=0, has_issue=0, imported_from="t")


with get_connection(DB) as conn:
    set_setting(conn, "current_month", "2026-06")
    a = upsert_employee(conn, no_staff="667", nama="SUFFI", dept="Ops")
    b = upsert_employee(conn, no_staff="41", nama="DIANA", dept="Kasir")
    att(conn, a, "2026-06-03", "08:10", "18:53")
    att(conn, a, "2026-06-05", "08:07", "22:36")
    att(conn, b, "2026-06-19", "08:00", "18:43")
    att(conn, b, "2026-06-26", "08:00", "19:25")

root = ctk.CTk()
root.withdraw()


def screen():
    s = screen_mod.OvertimeScreen(root)
    root.update_idletasks()
    return s


def click(s, prefix):
    lab = [l for l in s._filter_ctl.cget("values") if l.startswith(prefix)][0]
    s._filter_ctl._buttons_dict[lab].invoke()
    root.update_idletasks()
    return lab


def visible(s):
    return [s.tree.item(i, "values")[8] for i in s.tree.get_children()]


results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}")


# A) Tandai via dialog dari tab Semua
s = screen()
row = [r for r in s._rows if r.tanggal == "2026-06-03"][0]
dlg_mod.OvertimeDetailDialog(root, row, on_saved=s._on_detail_saved)._apply(
    "tidak_diterima")
root.update_idletasks()
click(s, "Tidak Diterima")
check("A dialog->tab Tidak Diterima", visible(s) == ["Tidak Diterima"],
      str(visible(s)))
s.destroy()

# B) Batch Ajukan baris Open
s = screen()
iid = [i for i, r in s._row_by_iid.items() if r.tanggal == "2026-06-19"][0]
s._toggle_check(iid)
s._apply_batch("diajukan")
root.update_idletasks()
click(s, "Diajukan")
check("B batch->tab Diajukan", visible(s) == ["Diajukan"], str(visible(s)))
s.destroy()

# C) Import bulan baru mengubah current_month -> daftar bulan lama kosong
with get_connection(DB) as conn:
    set_setting(conn, "current_month", "2026-07")   # efek import auto-detect
s = screen()
check("C1 pindah bulan otomatis: daftar kosong", visible(s) == [],
      f"bulan={s._month} rows={len(s._rows)}")
s.destroy()
with get_connection(DB) as conn:
    set_setting(conn, "current_month", "2026-06")
s = screen()
click(s, "Semua")
check("C2 kembali ke Juni: keputusan muncul lagi", len(visible(s)) == 4,
      str(visible(s)))
s.destroy()

# D) Edit baris dari Heatmap setelah keputusan
with get_connection(DB) as conn:
    save_manual_attendance(
        conn, employee_id=a, tanggal="2026-06-03", hari="Rabu",
        tipe="Hari Kerja", jadwal=None, masuk="08:10", keluar="18:53",
        kerja_jam=10.7, lembur_jam=2.7, terlambat_menit=0, has_issue=0)
    d = get_decision(conn, a, "2026-06-03")
check("D edit heatmap: keputusan tetap", d and d["status"] == "tidak_diterima",
      str(d and d["status"]))

# E) Resolve via Issues setelah keputusan
with get_connection(DB) as conn:
    rid = conn.execute(
        "SELECT id FROM attendance_records WHERE employee_id=? AND tanggal=?",
        (a, "2026-06-05")).fetchone()["id"]
    set_reason(conn, attendance_id=rid, category="tugas_lapangan", detail="X")
    d = get_decision(conn, a, "2026-06-05")
check("E resolve Issues: keputusan tetap", d and d["status"] == "diterima",
      str(d and d["status"]))

# F) Tandai libur setelah keputusan
with get_connection(DB) as conn:
    mark_holidays(conn, ["2026-06-05"])
    d = get_decision(conn, a, "2026-06-05")
check("F tandai libur: keputusan tetap", d and d["status"] == "diterima")

# G) Restore backup
snap_before = create_backup(DB, reason="test-sebelum")
with get_connection(DB) as conn:
    apply_status(conn, employee_id=b, tanggal="2026-06-26",
                 status="diterima", detected_minutes=205,
                 approved_minutes=205)
snap_after = create_backup(DB, reason="test-sesudah")
restore_backup(DB, snap_before)      # kembali ke sebelum keputusan b
with get_connection(DB) as conn:
    d = get_decision(conn, b, "2026-06-26")
check("G1 restore snapshot lama: keputusan hilang (by design)",
      d is None, str(d and d["status"]))
restore_backup(DB, snap_after)       # kembali ke sesudah keputusan b
with get_connection(DB) as conn:
    d = get_decision(conn, b, "2026-06-26")
check("G2 restore snapshot baru: keputusan ada", d and d["status"] == "diterima")

# H) Restart aplikasi (layar baru)
s = screen()
click(s, "Semua")
check("H restart: 4 baris + status utuh", len(visible(s)) == 4,
      str(visible(s)))
s.destroy()

root.destroy()
print()
failed = [r for r in results if not r[1]]
print(f"total={len(results)} pass={len(results) - len(failed)} "
      f"fail={len(failed)}")
