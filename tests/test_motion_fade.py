"""Item 08 & 12 — satu-satunya fade sungguhan yang mungkin di Tk."""
import time
import tkinter as tk

from src.ui import motion


def test_fade_window_berakhir_di_alpha_penuh(tk_root):
    motion.set_enabled(False)
    top = tk.Toplevel(tk_root)
    try:
        motion.fade_window(top)
        assert float(top.attributes("-alpha")) == 1.0
    finally:
        top.destroy()


def test_fade_window_aman_di_jendela_yang_sudah_hancur(tk_root):
    motion.set_enabled(True)
    top = tk.Toplevel(tk_root)
    motion.fade_window(top)
    top.destroy()
    tk_root.update()          # tidak boleh melempar TclError


def test_fade_window_tidak_meledak_bila_alpha_tak_didukung(tk_root, monkeypatch):
    """Di platform tanpa dukungan -alpha, jendela harus tetap tampil penuh."""
    motion.set_enabled(True)
    top = tk.Toplevel(tk_root)
    try:
        def boom(*a, **k):
            raise tk.TclError("bad option -alpha")
        monkeypatch.setattr(top, "attributes", boom)
        motion.fade_window(top)     # tidak boleh melempar
    finally:
        top.destroy()


def test_fade_window_benar_benar_memudar_saat_motion_menyala(tk_root):
    """Buktikan animasinya nyata, bukan cuma keadaan akhir yang benar.

    Dengan motion menyala, alpha harus mulai di 0.0 (transparan) dan hanya
    naik ke 1.0 setelah beberapa frame — kalau fade_window diam-diam
    melompat langsung ke alpha penuh, pengujian ini gagal di langkah awal.
    """
    motion.set_enabled(True)
    try:
        top = tk.Toplevel(tk_root)
        try:
            motion.fade_window(top)
            # segera setelah dipanggil (sebelum event loop dipompa), jendela
            # harus masih di alpha 0 — bukti fade dimulai dari transparan.
            first_alpha = float(top.attributes("-alpha"))
            assert first_alpha < 1.0, "jendela harus mulai transparan, bukan langsung penuh"

            t0 = time.perf_counter()
            while float(top.attributes("-alpha")) < 1.0 and time.perf_counter() - t0 < 3.0:
                tk_root.update()
            assert float(top.attributes("-alpha")) == 1.0, "jendela tidak pernah mencapai alpha penuh"
        finally:
            top.destroy()
    finally:
        motion.set_enabled(False)


def test_fade_jendela_utama_dipicu_setelah_jendela_dimunculkan():
    """Regresi urutan startup (item 12).

    main.py mengonstruksi HRApp lalu SEGERA withdraw() sebelum splash tampil;
    deiconify() baru terjadi ~2 detik kemudian. Tween 170ms yang dimulai di
    konstruktor akan tuntas dalam keadaan tersembunyi, jadi fade-nya tidak
    pernah terlihat user — animasinya benar dan teruji, tapi tidak terkirim.

    Pemicunya harus ada di _reveal(), SETELAH deiconify.
    """
    import inspect
    import src.main as main_mod
    import src.ui.app as app_mod

    src = inspect.getsource(main_mod.main)
    assert "motion.fade_window(app)" in src, \
        "fade jendela utama tidak dipicu dari main.py"
    assert src.index("app.deiconify()") < src.index("motion.fade_window(app)"), \
        "fade dipicu sebelum jendela dimunculkan — tidak akan terlihat"
    assert src.index('app.attributes("-alpha", 0.0)') < src.index("app.deiconify()"), \
        "jendela tidak dibuat transparan sebelum tampil — akan berkedip dulu"

    assert "motion.fade_window(self)" not in inspect.getsource(app_mod.HRApp.__init__), \
        "fade masih dipicu di konstruktor; di sana jendela masih withdrawn"
