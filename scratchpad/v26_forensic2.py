"""Forensik lanjutan: journal/WAL, timestamp keputusan, integritas DB."""
import shutil
import sqlite3
import tempfile
from pathlib import Path

DATA = Path(r"C:\Users\user\AppData\Local\Programs\HR-Absensi\data")
print("isi folder data:")
for f in sorted(DATA.iterdir()):
    print(f"  {f.name:32} {f.stat().st_size:>12,} bytes")

DB = DATA / "hr.db"
cp = Path(tempfile.gettempdir()) / "v26_forensic.db"
shutil.copy2(DB, cp)
con = sqlite3.connect(cp)
con.row_factory = sqlite3.Row

print("\nintegritas:", con.execute("PRAGMA integrity_check").fetchone()[0])
print("journal_mode:", con.execute("PRAGMA journal_mode").fetchone()[0])

print("\nkeputusan lembur (lengkap):")
for r in con.execute(
        "SELECT employee_id, tanggal, status, approved_minutes, "
        "detected_minutes_at_decision, submitted_at, decided_at, updated_at "
        "FROM overtime_decisions ORDER BY tanggal").fetchall():
    print("  ", tuple(r))

print("\nimport terakhir (export_history/imported_at):")
for r in con.execute(
        "SELECT MAX(imported_at) mx FROM attendance_records").fetchall():
    print("   imported_at terakhir:", tuple(r))
for r in con.execute(
        "SELECT imported_from, imported_at, COUNT(*) n FROM attendance_records "
        "GROUP BY imported_from ORDER BY imported_at DESC LIMIT 5").fetchall():
    print("  ", tuple(r))

print("\nsemua baris absensi > 18:00 per bulan (kandidat lembur):")
for r in con.execute(
        "SELECT substr(tanggal,1,7) m, COUNT(*) n FROM attendance_records "
        "WHERE keluar > '18:00' GROUP BY m ORDER BY m").fetchall():
    print("  ", tuple(r))
con.close()
