"""Item 05 — sapuan heatmap, dan jaminan ia tidak menyala saat mencari."""
import tkinter as tk

from src.ui import motion


def test_wipe_mendarat_di_warna_tujuan_saat_motion_mati(tk_root):
    motion.set_enabled(False)
    cv = tk.Canvas(tk_root, width=200, height=60)
    items = [cv.create_rectangle(i * 10, 0, i * 10 + 8, 20,
                                 fill="#10B981", tags=("cellrect",))
             for i in range(10)]
    motion.wipe_canvas(cv, "cellrect", "#141414")
    for it in items:
        assert cv.itemcget(it, "fill") == "#10B981"
    cv.destroy()


def test_wipe_tanpa_sel_tidak_meledak(tk_root):
    motion.set_enabled(False)
    cv = tk.Canvas(tk_root, width=50, height=20)
    motion.wipe_canvas(cv, "cellrect", "#141414")     # tidak ada item bertag itu
    cv.destroy()


def test_mengetik_di_pencarian_tidak_memicu_sapuan(tk_root, monkeypatch, tmp_path):
    """Regresi jebakan #1: _repaint() juga dipanggil _on_search (debounce
    200 ms), _on_sort, dan _apply_resize. Sapuan hanya boleh ikut saat
    sidik jari berubah — dan kata pencarian sengaja di luar sidik jari.

    NOTE penyesuaian dari rencana: butuh minimal satu baris attendance
    supaya build_heatmap_context() TIDAK menandai konteks "is_empty" —
    kalau tidak, _repaint() selalu mengambil jalur early-return kosong dan
    tidak pernah menyentuh _anim_sig sama sekali (sapuan memang tak pernah
    jalan, tapi itu bukan yang mau dibuktikan tes ini)."""
    from src.db.schema import init_db
    from src.db.connection import get_connection
    from src.db.settings import set_setting
    from src.db.employees import upsert_employee
    from src.db.attendance import upsert_attendance
    from src.ui.screens import heatmap as M

    p = tmp_path / "hr.db"
    init_db(p)
    with get_connection(p) as conn:
        set_setting(conn, "current_month", "2026-07")
        eid = upsert_employee(conn, no_staff="1", nama="ANDI", dept="IT")
        upsert_attendance(conn, employee_id=eid, tanggal="2026-07-01", hari="Rabu",
                          tipe="Hari Kerja", jadwal="", masuk="08:03", keluar="16:10",
                          kerja_jam=None, lembur_jam=None, terlambat_menit=3,
                          has_issue=0, imported_from="W")
    monkeypatch.setattr(M, "DB_PATH", p)

    s = M.HeatmapScreen(tk_root)
    try:
        parts = s._anim_parts()
        s._on_search("bud")
        assert s._anim_parts() == parts, \
            "kata pencarian bocor ke sidik jari — sapuan akan berkedip tiap ketukan"
        assert s._anim_sig.changed(*s._anim_parts()) is False
    finally:
        s.destroy()


def test_sapuan_benar_benar_menyapu_saat_motion_menyala(tk_root):
    """Tes lain di berkas ini semuanya negatif dan berjalan dengan motion
    MATI — di mana wipe_canvas langsung return. Artinya logika inti sapuan
    tidak pernah dieksekusi sama sekali. Yang ini menutup lubang itu:
    sel harus benar-benar dipadamkan dulu, lalu menyala kembali ke warna
    tujuannya, kolom demi kolom."""
    import time
    import tkinter as tk
    motion.set_enabled(True)
    try:
        cv = tk.Canvas(tk_root, width=400, height=60)
        cv.pack()
        target = "#10B981"
        items = [cv.create_rectangle(i * 14, 0, i * 14 + 12, 20,
                                     fill=target, width=0, tags=("cellrect",))
                 for i in range(20)]
        tk_root.update()

        motion.wipe_canvas(cv, "cellrect", "#141414")
        tk_root.update()
        padam = [i for i in items if cv.itemcget(i, "fill") == "#141414"]
        assert padam, "tidak ada sel yang dipadamkan — sapuan tidak berjalan"

        t0 = time.perf_counter()
        while time.perf_counter() - t0 < 3.0:
            tk_root.update()
            if all(cv.itemcget(i, "fill") == target for i in items):
                break
        assert all(cv.itemcget(i, "fill") == target for i in items), \
            "sel tidak kembali ke warna tujuan setelah sapuan selesai"
        cv.destroy()
    finally:
        motion.set_enabled(False)


def test_ganti_bulan_memicu_sapuan(tk_root, monkeypatch, tmp_path):
    """Sisi positif dari test_mengetik_di_pencarian_tidak_memicu_sapuan:
    kalau sidik jarinya terlalu ketat, sapuan tidak akan pernah jalan sama
    sekali dan semua tes negatif tetap lulus."""
    from src.db.schema import init_db
    from src.db.connection import get_connection
    from src.db.settings import set_setting
    from src.ui.screens import heatmap as M

    p = tmp_path / "hr.db"
    init_db(p)
    with get_connection(p) as conn:
        set_setting(conn, "current_month", "2026-07")
    monkeypatch.setattr(M, "DB_PATH", p)

    s = M.HeatmapScreen(tk_root)
    try:
        s._month = "2026-08"
        assert s._anim_sig.changed(*s._anim_parts()) is True, \
            "ganti bulan tidak mengubah sidik jari — sapuan tidak akan pernah jalan"
    finally:
        s.destroy()


def test_bump_data_version_memicu_sapuan(tk_root, monkeypatch, tmp_path):
    """Import baru / resolve menaikkan data_version; heatmap harus menyapu
    ulang karena isinya memang berubah."""
    from src.core.session_state import notify_data_changed
    from src.db.schema import init_db
    from src.db.connection import get_connection
    from src.db.settings import set_setting
    from src.ui.screens import heatmap as M

    p = tmp_path / "hr.db"
    init_db(p)
    with get_connection(p) as conn:
        set_setting(conn, "current_month", "2026-07")
    monkeypatch.setattr(M, "DB_PATH", p)

    s = M.HeatmapScreen(tk_root)
    try:
        s._anim_sig.changed(*s._anim_parts())          # catat keadaan sekarang
        notify_data_changed()
        assert s._anim_sig.changed(*s._anim_parts()) is True
    finally:
        s.destroy()
