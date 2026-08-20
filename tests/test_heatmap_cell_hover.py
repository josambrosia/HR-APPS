"""Item 06 — sel yang disorot ditandai; tooltip memudar, tidak menjeplak."""
import tkinter as tk


def _screen(tk_root, monkeypatch, tmp_path):
    from src.db.schema import init_db
    from src.db.connection import get_connection
    from src.db.settings import set_setting
    from src.ui.screens import heatmap as M
    p = tmp_path / "hr.db"
    init_db(p)
    with get_connection(p) as conn:
        set_setting(conn, "current_month", "2026-07")
    monkeypatch.setattr(M, "DB_PATH", p)
    return M.HeatmapScreen(tk_root)


def test_menyorot_sel_memberi_outline_dan_melepasnya_lagi(tk_root, monkeypatch, tmp_path):
    s = _screen(tk_root, monkeypatch, tmp_path)
    try:
        cv = s._canvas
        item = cv.create_rectangle(0, 0, 10, 10, fill="#10B981", outline="")
        s._highlight_cell(item)
        assert cv.itemcget(item, "outline") != ""
        s._highlight_cell(None)
        assert cv.itemcget(item, "outline") == ""
    finally:
        s.destroy()


def test_tooltip_mulai_transparan_lalu_terlihat(tk_root, monkeypatch, tmp_path):
    from src.ui import motion
    motion.set_enabled(False)
    s = _screen(tk_root, monkeypatch, tmp_path)
    try:
        cell = {"label": "Senin", "date": "03", "masuk": "07.58",
                "keluar": "16.05", "telat": "0", "alasan": "-"}
        evt = tk.Event()
        evt.x_root, evt.y_root = 100, 100
        s._show_tip(evt, cell)
        assert float(s._tip.attributes("-alpha")) == 1.0
    finally:
        s.destroy()


def test_tooltip_benar_benar_memudar_saat_motion_menyala(tk_root, monkeypatch, tmp_path):
    """Buktikan animasinya nyata, bukan cuma keadaan akhir yang benar.

    Dengan motion menyala, frame pertama harus alpha 0 (baru dipasang), lalu
    setelah dipompa beberapa langkah alpha naik tapi belum tentu 1.0, dan
    akhirnya mendarat di 1.0. Kalau `_show_tip` diam-diam melompat langsung
    ke alpha penuh (mis. lupa tween), pengujian ini akan gagal di langkah
    tengah.
    """
    from src.ui import motion
    motion.set_enabled(True)
    try:
        s = _screen(tk_root, monkeypatch, tmp_path)
        try:
            cell = {"label": "Senin", "date": "03", "masuk": "07.58",
                    "keluar": "16.05", "telat": "0", "alasan": "-"}
            evt = tk.Event()
            evt.x_root, evt.y_root = 100, 100

            s._show_tip(evt, cell)
            # tepat setelah dipanggil (sebelum polling), alpha harus 0 — bukti
            # bahwa fade dimulai dari transparan, bukan langsung penuh.
            first_alpha = float(s._tip.attributes("-alpha"))
            assert first_alpha < 1.0, "tooltip harus mulai transparan, bukan langsung penuh"

            import time
            t0 = time.perf_counter()
            while float(s._tip.attributes("-alpha")) < 1.0 and time.perf_counter() - t0 < 3.0:
                tk_root.update()
            assert float(s._tip.attributes("-alpha")) == 1.0, "tooltip tidak pernah mencapai alpha penuh"
        finally:
            s.destroy()
    finally:
        motion.set_enabled(False)


def _seeded_screen(tk_root, monkeypatch, tmp_path):
    """Heatmap dengan data nyata, supaya kanvasnya benar-benar terisi item."""
    from datetime import date, timedelta
    from src.db.schema import init_db
    from src.db.connection import get_connection
    from src.db.settings import set_setting
    from src.db.employees import upsert_employee
    from src.db.attendance import save_manual_attendance
    from src.ui.screens import heatmap as M

    p = tmp_path / "hr.db"
    init_db(p)
    with get_connection(p) as conn:
        set_setting(conn, "current_month", "2026-07")
        eid = upsert_employee(conn, no_staff="S1", nama="Andi", dept="Ops")
        d = date(2026, 7, 1)
        while d.month == 7:
            if d.weekday() < 5:
                telat = 60 if d.day % 5 == 0 else (10 if d.day % 3 == 0 else 0)
                save_manual_attendance(
                    conn, employee_id=eid, tanggal=d.isoformat(), hari="Senin",
                    tipe="Hari Kerja", jadwal="08.00 - 16.00",
                    masuk="08:00", keluar="16:00", kerja_jam=8.0,
                    lembur_jam=0.0, terlambat_menit=telat, has_issue=0)
            d += timedelta(days=1)
    monkeypatch.setattr(M, "DB_PATH", p)
    s = M.HeatmapScreen(tk_root)
    s.pack()
    tk_root.update()
    return s


def test_menyorot_SETIAP_item_yang_bisa_disorot_tidak_melempar(tk_root, monkeypatch, tmp_path):
    """Regresi yang ditemukan smoke, bukan oleh 743 tes.

    _cell_by_item memetakan kotak sel DAN teks angka tanggalnya ke sel yang
    sama. Item teks di Canvas tidak punya opsi -outline sama sekali, jadi
    begitu kursor lewat di atas angka tanggal — bukan kotaknya — handler
    melempar TclError: unknown option "-outline". Hal yang sama berlaku untuk
    label menit di grafik keterlambatan.

    Aplikasi tidak mati (Tkinter menelan error callback) sehingga tes "apakah
    masih hidup" pun lolos — tapi sorotannya rusak dan konsol dibanjiri
    traceback. Tes ini menelusuri SETIAP item bertag 'cell' yang benar-benar
    tergambar, bukan hanya kotak yang dibuat tes secara manual.
    """
    s = _seeded_screen(tk_root, monkeypatch, tmp_path)
    try:
        items = s._canvas.find_withtag("cell")
        assert len(items) > 20, f"kanvas nyaris kosong ({len(items)} item) — tes tidak berarti"

        jenis = {s._canvas.type(i) for i in items}
        assert "text" in jenis, "tidak ada item teks — justru itu yang dulu melempar"

        for item in items:
            target = s._hover_rect_by_item.get(item)
            s._highlight_cell(target)      # tidak boleh melempar untuk item apa pun
        s._highlight_cell(None)
    finally:
        s.destroy()


def test_menyorot_angka_tanggal_menandai_kotaknya(tk_root, monkeypatch, tmp_path):
    """Bukan sekadar tidak melempar: menyorot teks harus menandai KOTAKNYA,
    supaya sorotannya tetap terlihat."""
    s = _seeded_screen(tk_root, monkeypatch, tmp_path)
    try:
        teks = [i for i in s._canvas.find_withtag("cell")
                if s._canvas.type(i) == "text"]
        assert teks, "prasyarat: ada item teks"
        item = teks[0]
        target = s._hover_rect_by_item.get(item)
        assert target is not None and s._canvas.type(target) == "rectangle", \
            "angka tanggal tidak dipetakan ke kotaknya"
        s._highlight_cell(target)
        assert s._canvas.itemcget(target, "outline") != ""
    finally:
        s.destroy()
