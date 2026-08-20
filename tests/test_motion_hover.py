# tests/test_motion_hover.py
"""Hover: item nav (01) dan chip bulan aktif (14)."""
import customtkinter as ctk

from src.ui import motion
from src.ui.app import HRApp
from src.ui.theme import COLOR_SURFACE, COLOR_ACCENT_TINT_BG


def test_hover_tint_mencapai_warna_tujuan_saat_motion_mati(tk_root):
    motion.set_enabled(False)
    f = ctk.CTkFrame(tk_root, fg_color="#0A0A0A")
    motion.hover_tint(f, "#0A0A0A", COLOR_SURFACE)
    assert f.cget("fg_color") == COLOR_SURFACE
    f.destroy()


def test_hover_tint_balik_ke_warna_asal(tk_root):
    motion.set_enabled(False)
    f = ctk.CTkFrame(tk_root, fg_color="#0A0A0A")
    motion.hover_tint(f, "#0A0A0A", COLOR_SURFACE)
    motion.hover_tint(f, COLOR_SURFACE, "#0A0A0A")
    assert f.cget("fg_color") == "#0A0A0A"
    f.destroy()


class _SidebarHarness(ctk.CTkFrame):
    """Sidebar asli tanpa membuat root Tk kedua.

    Mengonstruksi HRApp() di dalam tes akan membuat ctk.CTk() kedua di
    samping fixture tk_root yang berlingkup sesi — Tk di Windows tidak
    bisa itu, dan hasilnya tes ngambang yang bergantung urutan (persis
    yang kita perbaiki di v24). Proyek ini sudah punya pola yang sama di
    tests/test_app_caching.py::_ShellHarness.
    """
    _build_sidebar = HRApp._build_sidebar
    _build_nav_item = HRApp._build_nav_item
    _set_active_nav_item = HRApp._set_active_nav_item
    _load_sidebar_icon = HRApp._load_sidebar_icon
    _format_active_month_label = HRApp._format_active_month_label

    def __init__(self, root):
        super().__init__(root)
        self._nav_items = {}
        self._active_nav_key = "Dashboard"
        self._build_sidebar()

    def _show(self, name):
        self._set_active_nav_item(name)


def test_chip_bulan_aktif_punya_umpan_balik_hover(tk_root):
    """Regresi cacat: chip bisa diklik + berkursor tangan tapi tidak
    bereaksi saat disorot, jadi tidak ada yang menandakan ia interaktif.

    CTkFrame.bind() sendiri selalu mengembalikan None saat dipakai untuk
    query (bug/keterbatasan customtkinter — implementasinya tidak me-return
    hasil dari canvas internal). Binding sungguhan didelegasikan ke
    `._canvas`, jadi query yang benar dilakukan di sana.
    """
    h = _SidebarHarness(tk_root)
    try:
        binds = h._active_month_chip._canvas.bind()
        assert "<Enter>" in binds, "chip tidak punya umpan balik hover"
        assert "<Leave>" in binds
    finally:
        h.destroy()


def test_hover_chip_mengubah_warna_lalu_mengembalikannya(tk_root):
    motion.set_enabled(False)
    h = _SidebarHarness(tk_root)
    # event_generate hanya memicu binding kalau widget benar-benar ter-map
    # (geometri sudah diproses oleh window manager) — bukan cuma dikonstruksi
    # dan di-pack. tk_root sengaja di-withdraw() sepanjang sesi tes (lihat
    # conftest.py::tk_root) supaya tidak ada jendela yang berkedip selama
    # suite jalan, jadi widget di dalamnya tidak pernah ter-map secara
    # normal. Deiconify sesaat di sini, lalu withdraw lagi di finally,
    # supaya tes ini tetap memverifikasi event Tk sungguhan tanpa membocorkan
    # visibilitas jendela ke tes lain.
    h.pack()
    tk_root.deiconify()
    tk_root.update()
    try:
        chip = h._active_month_chip
        assert chip.winfo_ismapped(), "chip tidak ter-map — event_generate tidak akan memicu binding"
        # Event Enter/Leave sungguhan diterima oleh canvas internal CTkFrame,
        # bukan oleh frame Tk luar — lihat catatan di tes sebelumnya.
        chip._canvas.event_generate("<Enter>")
        tk_root.update()
        assert chip.cget("fg_color") != COLOR_ACCENT_TINT_BG
        chip._canvas.event_generate("<Leave>")
        tk_root.update()
        assert chip.cget("fg_color") == COLOR_ACCENT_TINT_BG
    finally:
        tk_root.withdraw()
        h.destroy()
