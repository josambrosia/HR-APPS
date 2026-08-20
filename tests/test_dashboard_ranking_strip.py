"""Regresi: pegawai resign masih muncul di Ranking Lengkap, dan itu sempat
menjatuhkan aplikasi sejak startup.

Penyebab nyata (dilaporkan pemakai, v24.0.1): seorang pegawai resign
(active=0) tetapi masih punya data absensi di bulan aktif. Ranking Lengkap
tetap memuatnya, sedangkan peta status kehadiran dibangun dari daftar pegawai
AKTIF saja — jadi barisnya tidak punya strip.

Baris tanpa strip mengirim `image=None` ke Treeview.insert. tkinter
_format_optdict MENGHAPUS nilai None tapi tetap menulis nama opsinya, sehingga
panggilan Tcl menjadi `-image -values {...}`: `-values` termakan sebagai nilai
`-image`, lalu daftar nilai dibaca sebagai nama opsi —
  TclError: unknown option "PUTRI {ARGA DIRGA} {46 mnt} 2 1"
Dashboard adalah layar pertama, jadi aplikasi mati sebelum bisa dibuka.
"""
from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.attendance import upsert_attendance
from src.db.settings import set_setting

MONTH = "2026-05"


def _late_row(conn, eid, day, telat):
    upsert_attendance(
        conn, employee_id=eid, tanggal=f"{MONTH}-{day:02d}", hari="Senin",
        tipe="Hari Kerja", jadwal="08.00 - 16.00", masuk="08:20", keluar="16:00",
        kerja_jam=7.6, lembur_jam=0.0, terlambat_menit=telat, has_issue=0,
        imported_from="t.xls")


def _db(path, *, resign=True):
    """Dua pegawai dengan keterlambatan; salah satunya resign (active=0)."""
    init_db(path)
    with get_connection(path) as conn:
        set_setting(conn, "current_month", MONTH)
        stay = upsert_employee(conn, no_staff="S1", nama="ANDI", dept="OPS")
        gone = upsert_employee(conn, no_staff="S2", nama="PUTRI", dept="ARGA DIRGA")
        for day, telat in ((4, 20), (5, 26)):
            _late_row(conn, stay, day, telat)
            _late_row(conn, gone, day, telat)
        if resign:
            conn.execute("UPDATE employees SET active = 0 WHERE id = ?", (gone,))
    return path


def test_resigned_employee_row_does_not_crash_dashboard(temp_db_path, monkeypatch, tk_root):
    import src.ui.screens.dashboard as mod
    monkeypatch.setattr(mod, "DB_PATH", _db(temp_db_path))
    screen = mod.DashboardScreen(tk_root)          # dulu: TclError di sini
    try:
        tk_root.update_idletasks()
        names = [screen.rank_tree.item(i, "values")[0]
                 for i in screen.rank_tree.get_children()]
        assert "PUTRI" in names, "pegawai resign tetap ditampilkan apa adanya"
        assert "ANDI" in names
    finally:
        screen.destroy()


def test_resigned_row_loses_only_its_strip(temp_db_path, monkeypatch, tk_root):
    """Degradasi yang benar: barisnya tetap ada, hanya strip-nya kosong —
    sementara baris pegawai aktif tetap bergambar."""
    import src.ui.screens.dashboard as mod
    monkeypatch.setattr(mod, "DB_PATH", _db(temp_db_path))
    screen = mod.DashboardScreen(tk_root)
    try:
        tk_root.update_idletasks()
        by_name = {screen.rank_tree.item(i, "values")[0]: i
                   for i in screen.rank_tree.get_children()}
        assert not screen.rank_tree.item(by_name["PUTRI"], "image")
        assert screen.rank_tree.item(by_name["ANDI"], "image")
    finally:
        screen.destroy()


def test_all_rows_keep_strips_when_nobody_resigned(temp_db_path, monkeypatch, tk_root):
    """Jalur normal tidak boleh ikut kehilangan gambar saat memperbaiki None."""
    import src.ui.screens.dashboard as mod
    monkeypatch.setattr(mod, "DB_PATH", _db(temp_db_path, resign=False))
    screen = mod.DashboardScreen(tk_root)
    try:
        tk_root.update_idletasks()
        rows = screen.rank_tree.get_children()
        assert len(rows) == 2
        assert all(screen.rank_tree.item(i, "image") for i in rows)
    finally:
        screen.destroy()


def test_survives_status_map_failure(temp_db_path, monkeypatch, tk_root):
    """Kegagalan peta status ditelan `except` -> SEMUA baris tanpa strip.
    Harus tetap tampil, bukan crash."""
    import src.ui.screens.dashboard as mod
    monkeypatch.setattr(mod, "DB_PATH", _db(temp_db_path, resign=False))
    monkeypatch.setattr(mod, "month_status_map",
                        lambda conn, month: (_ for _ in ()).throw(RuntimeError("boom")))
    screen = mod.DashboardScreen(tk_root)
    try:
        tk_root.update_idletasks()
        assert len(screen.rank_tree.get_children()) == 2
    finally:
        screen.destroy()
