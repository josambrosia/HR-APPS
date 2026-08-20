"""Item 02 — garis nav aktif meluncur, bukan hilang lalu muncul."""
from src.ui import motion
from tests.test_motion_hover import _SidebarHarness


def test_hanya_ada_satu_garis_aktif_untuk_seluruh_sidebar(tk_root):
    """Regresi arsitektur: sebelumnya tiap item punya garisnya sendiri, jadi
    mustahil meluncur. Sekarang satu garis dipakai bersama."""
    h = _SidebarHarness(tk_root)
    try:
        assert hasattr(h, "_nav_indicator")
        for item in h._nav_items.values():
            assert not hasattr(item, "_left_bar"), \
                "garis per-item masih ada — luncuran tidak akan mungkin"
    finally:
        h.destroy()


def test_garis_pindah_ke_posisi_item_yang_dipilih(tk_root):
    # Perlu jendela benar-benar map/deiconify — di dalam sesi withdraw()
    # winfo_y() tidak dapat dipercaya (window manager belum menata geometri).
    # Lihat pola yang sama di
    # test_motion_hover.py::test_hover_chip_mengubah_warna_lalu_mengembalikannya.
    motion.set_enabled(False)
    h = _SidebarHarness(tk_root)
    h.pack()
    tk_root.deiconify()
    tk_root.update()
    try:
        h._set_active_nav_item("Heatmap")
        tk_root.update()
        y_heatmap = h._nav_indicator.winfo_y()
        h._set_active_nav_item("Coaching")
        tk_root.update()
        y_coaching = h._nav_indicator.winfo_y()
        assert y_coaching != y_heatmap, "garis tidak berpindah"
        # Target = tengah vertikal item (formula sama dengan _set_active_nav_item).
        # Tinggi item nyata dipengaruhi scaling DPI CTk (bisa > 32 yang
        # dikonfigurasi), jadi bandingkan dengan formula yang sama alih-alih
        # angka toleransi tetap yang mengasumsikan tinggi 32px.
        item = h._nav_items["Coaching"]
        target = item.winfo_y() + (item.winfo_height() - 22) // 2
        assert y_coaching == target, "garis tidak mendarat di item tujuan"
    finally:
        tk_root.withdraw()
        h.destroy()


def test_garis_terlihat_setelah_item_pertama_diaktifkan(tk_root):
    h = _SidebarHarness(tk_root)
    h.pack()
    tk_root.deiconify()
    tk_root.update()
    try:
        h._set_active_nav_item("Dashboard")
        tk_root.update()
        assert h._nav_indicator.winfo_ismapped()
    finally:
        tk_root.withdraw()
        h.destroy()


def _center_y(item):
    """Rumus pemusatan yang sama dengan _set_active_nav_item."""
    from src.ui.app import NAV_INDICATOR_H
    return item.winfo_y() + (item.winfo_height() - NAV_INDICATOR_H) // 2


def test_penempatan_PERTAMA_juga_mendarat_tepat(tk_root):
    """Regresi DPI: aktivasi pertama memakai place(), bukan place_configure().

    CTkFrame menskalakan koordinat di place() (pada DPI 125%, y=302 mendarat
    di 378) tapi TIDAK di place_configure(). Karena aktivasi pertama terjadi
    saat aplikasi baru dibuka, garisnya meleset ~76px dan bisa menempel di
    menu yang salah — sementara di layar 100% semuanya tampak normal, jadi
    bug seperti ini lolos ke pengguna. Indikatornya kini tk.Frame yang
    memakai piksel apa adanya di kedua jalur.
    """
    motion.set_enabled(False)
    h = _SidebarHarness(tk_root)
    h.pack()
    tk_root.deiconify()
    tk_root.update()
    try:
        assert not h._nav_indicator.winfo_ismapped(), \
            "prasyarat tes: indikator harus belum tampil sebelum aktivasi pertama"
        h._set_active_nav_item("Heatmap")     # <- jalur place(), bukan place_configure()
        tk_root.update()
        assert h._nav_indicator.winfo_y() == _center_y(h._nav_items["Heatmap"])
    finally:
        tk_root.withdraw()
        h.destroy()


def test_garis_terpusat_vertikal_di_itemnya(tk_root):
    """Celah atas dan bawah harus seimbang (selisih <=1px karena pembagian
    bulat). Kalau tinggi garis ikut terskala DPI sementara rumusnya tidak,
    garis akan menempel ke bawah."""
    motion.set_enabled(False)
    h = _SidebarHarness(tk_root)
    h.pack()
    tk_root.deiconify()
    tk_root.update()
    try:
        h._set_active_nav_item("Coaching")
        tk_root.update()
        item, ind = h._nav_items["Coaching"], h._nav_indicator
        atas = ind.winfo_y() - item.winfo_y()
        bawah = (item.winfo_y() + item.winfo_height()) - (ind.winfo_y() + ind.winfo_height())
        assert abs(atas - bawah) <= 1, f"garis tidak terpusat: atas={atas} bawah={bawah}"
    finally:
        tk_root.withdraw()
        h.destroy()
