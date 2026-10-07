"""v26 fix: area menu sidebar bisa discroll sehingga menu terakhir tidak
terpotong di layar pendek (sebelumnya semua item di-pack langsung di sidebar
dan tergeser keluar area terlihat)."""
import customtkinter as ctk

from tests.test_motion_hover import _SidebarHarness


def test_nav_area_is_scrollable(tk_root):
    h = _SidebarHarness(tk_root)
    try:
        assert isinstance(h._nav_parent, ctk.CTkScrollableFrame)
        # Container scroll (frame pembungkus) menempel langsung di sidebar.
        assert h._nav_parent._parent_frame in h.sidebar.winfo_children()
    finally:
        h.destroy()


def test_all_nav_items_live_inside_scroll_area(tk_root):
    h = _SidebarHarness(tk_root)
    try:
        for item in h._nav_items.values():
            assert item.winfo_parent() == str(h._nav_parent), \
                "item nav harus di dalam area scroll"
    finally:
        h.destroy()


def test_indicator_scrolls_with_content(tk_root):
    """Garis aktif satu parent dengan item agar koordinat y-nya sinkron
    walau area discroll."""
    h = _SidebarHarness(tk_root)
    try:
        assert h._nav_indicator.winfo_parent() == str(h._nav_parent)
    finally:
        h.destroy()


def test_sidebar_keeps_fixed_header_and_footer(tk_root):
    """Header + chip bulan + footer tetap anak langsung sidebar (tidak ikut
    discroll)."""
    h = _SidebarHarness(tk_root)
    try:
        direct = h.sidebar.winfo_children()
        assert h._active_month_chip in direct
        assert h._nav_parent._parent_frame in direct
        assert len(direct) >= 4   # header, chip, footer, wadah scroll
    finally:
        h.destroy()
