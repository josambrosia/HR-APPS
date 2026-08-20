"""Item 07 — bar papan peringkat tumbuh dari nol."""
import time

import customtkinter as ctk

from src.ui import motion
from src.ui.screens.dinas_recap import _make_metric_bar


def test_bar_mendarat_di_persen_tujuan_saat_motion_mati(tk_root):
    motion.set_enabled(False)
    host = ctk.CTkFrame(tk_root)
    bar = _make_metric_bar(host, "#0D9488")
    motion.grow_bar(bar, 76)
    assert bar._pct == 76
    host.destroy()


def test_bar_nol_persen_tetap_nol(tk_root):
    motion.set_enabled(False)
    host = ctk.CTkFrame(tk_root)
    bar = _make_metric_bar(host, "#0D9488")
    bar._pct = 50
    motion.grow_bar(bar, 0)
    assert bar._pct == 0
    host.destroy()


def test_bar_benar_benar_tumbuh_saat_motion_menyala(tk_root):
    """Buktikan gerakannya nyata, bukan cuma keadaan akhir yang benar.

    Dengan motion menyala, `_pct` harus melewati nilai antara sebelum
    mendarat tepat di target — kalau grow_bar diam-diam melompat langsung
    ke nilai akhir (mis. lupa tween), pengujian ini gagal di langkah tengah.
    """
    motion.set_enabled(True)
    try:
        host = ctk.CTkFrame(tk_root)
        bar = _make_metric_bar(host, "#0D9488")
        seen = []
        from src.ui.screens import dinas_recap as M

        real_draw = M._draw_metric_bar

        def spy(canvas):
            if canvas is bar:
                seen.append(canvas._pct)
            return real_draw(canvas)

        M._draw_metric_bar = spy
        try:
            motion.grow_bar(bar, 80)
            t0 = time.perf_counter()
            while bar._pct < 80 and time.perf_counter() - t0 < 3.0:
                tk_root.update()
        finally:
            M._draw_metric_bar = real_draw

        assert bar._pct == 80, "bar tidak pernah mencapai persentase tujuan"
        assert len(seen) > 1, "hanya satu frame digambar — bar melompat, tidak tumbuh"
        assert seen[0] < 80, "frame pertama sudah di nilai akhir — bukan pertumbuhan bertahap"
        assert all(b >= a for a, b in zip(seen, seen[1:])), "persentase harus monoton naik"
        host.destroy()
    finally:
        motion.set_enabled(False)
