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
