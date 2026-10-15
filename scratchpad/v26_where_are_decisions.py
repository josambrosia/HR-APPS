"""Cek dua DB + versi exe terinstall: di mana keputusan lembur berada?"""
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, r"D:\Gawe\Project X\HR App")

CANDIDATES = {
    "installed": Path(r"C:\Users\user\AppData\Local\Programs\HR-Absensi"),
    "dist": Path(r"D:\Gawe\Project X\HR App\dist\HR-Absensi"),
}

for name, root in CANDIDATES.items():
    print(f"===== {name}: {root} =====")
    exe = root / "HR-Absensi.exe"
    db = root / "data" / "hr.db"
    if exe.exists():
        st = exe.stat()
        print(f"exe  : {st.st_size:,} bytes · mtime {st.st_mtime}")
    else:
        print("exe  : (tidak ada)")
    if not db.exists():
        print("db   : (tidak ada)")
        continue
    cp = Path(tempfile.gettempdir()) / f"v26_check_{name}.db"
    shutil.copy2(db, cp)
    con = sqlite3.connect(cp)
    con.row_factory = sqlite3.Row
    tables = [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")]
    has = "overtime_decisions" in tables
    print(f"db   : overtime_decisions={'ADA' if has else 'TIDAK ADA'}")
    m = con.execute("SELECT value FROM settings WHERE key='current_month'").fetchone()
    print(f"       current_month={m['value'] if m else None!r}")
    if has:
        dec = con.execute(
            "SELECT employee_id, tanggal, status FROM overtime_decisions "
            "ORDER BY tanggal").fetchall()
        print(f"       decisions={len(dec)}")
        for r in dec:
            ar = con.execute(
                "SELECT COUNT(*) FROM attendance_records "
                "WHERE employee_id=? AND tanggal=?",
                (r["employee_id"], r["tanggal"])).fetchone()[0]
            print(f"         {r['tanggal']} emp={r['employee_id']} "
                  f"{r['status']:15} attendance_row={'ADA' if ar else 'HILANG'}")
    print("       bulan absensi:",
          [tuple(r) for r in con.execute(
              "SELECT substr(tanggal,1,7) m, COUNT(*) n FROM attendance_records "
              "GROUP BY m ORDER BY m")])
    con.close()
    print()
