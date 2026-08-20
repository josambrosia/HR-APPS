"""Mesin animasi v25 — fungsi murni, tween, registry pembatalan."""
import pytest

from src.ui import motion


@pytest.fixture(autouse=True)
def motion_on():
    """Tes di berkas ini menguji mesinnya, jadi harus menyala. Berjalan
    SETELAH fixture disable_motion di conftest (autouse berkas lebih dalam
    dieksekusi belakangan), sehingga menang."""
    motion.set_enabled(True)
    yield
    motion.set_enabled(False)


class TestLerpHex:
    def test_t_nol_mengembalikan_warna_awal(self):
        assert motion.lerp_hex("#000000", "#FFFFFF", 0.0) == "#000000"

    def test_t_satu_mengembalikan_warna_akhir(self):
        assert motion.lerp_hex("#000000", "#FFFFFF", 1.0) == "#FFFFFF"

    def test_titik_tengah_dibulatkan_konsisten(self):
        assert motion.lerp_hex("#000000", "#FFFFFF", 0.5) == "#7F7F7F"

    def test_menangani_warna_asli_aplikasi(self):
        # COLOR_BG -> COLOR_SURFACE_HIGH, dipakai hover nav
        assert motion.lerp_hex("#0A0A0A", "#1F1F1F", 1.0) == "#1F1F1F"

    def test_t_diluar_rentang_dijepit(self):
        assert motion.lerp_hex("#000000", "#FFFFFF", -3.0) == "#000000"
        assert motion.lerp_hex("#000000", "#FFFFFF", 9.0) == "#FFFFFF"

    def test_menolak_bentuk_singkat_tiga_digit(self):
        # Tk menerima #FFF, tapi lerp kita tidak — gagal keras, jangan diam-diam salah.
        with pytest.raises(ValueError):
            motion.lerp_hex("#FFF", "#000000", 0.5)


class TestEasing:
    @pytest.mark.parametrize("fn", [motion.linear, motion.ease_out_cubic,
                                    motion.ease_out_quint])
    def test_semua_easing_terikat_di_ujung(self, fn):
        assert fn(0.0) == pytest.approx(0.0)
        assert fn(1.0) == pytest.approx(1.0)

    def test_ease_out_mendahului_linear_di_tengah(self):
        assert motion.ease_out_cubic(0.5) > motion.linear(0.5)

    @pytest.mark.parametrize("fn", [motion.linear, motion.ease_out_cubic,
                                    motion.ease_out_quint])
    def test_semua_easing_monoton_naik(self, fn):
        vals = [fn(i / 20) for i in range(21)]
        assert all(b >= a for a, b in zip(vals, vals[1:]))


class TestEnabledFlag:
    def test_default_aktif(self):
        motion.set_enabled(True)
        assert motion.enabled() is True

    def test_bisa_dimatikan_dan_dinyalakan(self):
        motion.set_enabled(False)
        assert motion.enabled() is False
        motion.set_enabled(True)
        assert motion.enabled() is True

    def test_memuat_dari_setting_string(self, tmp_path):
        from src.db.schema import init_db
        from src.db.connection import get_connection
        from src.db.settings import set_setting

        p = tmp_path / "hr.db"
        init_db(p)
        with get_connection(p) as conn:
            set_setting(conn, "motion_enabled", "0")
        with get_connection(p) as conn:
            motion.load_enabled_from_db(conn)
        assert motion.enabled() is False

    def test_setting_belum_ada_berarti_aktif(self, tmp_path):
        from src.db.schema import init_db
        from src.db.connection import get_connection

        p = tmp_path / "hr.db"
        init_db(p)
        motion.set_enabled(False)          # pastikan benar-benar berubah
        with get_connection(p) as conn:
            motion.load_enabled_from_db(conn)
        assert motion.enabled() is True


class TestTweenDimatikan:
    def test_langsung_ke_frame_terakhir_tanpa_timer(self, tk_root):
        motion.set_enabled(False)
        seen = []
        done = []
        job = motion.tween(tk_root, 500, seen.append, on_done=lambda: done.append(1))
        assert job is None            # tidak ada timer yang dijadwalkan
        assert seen == [1.0]          # tepat satu frame: keadaan akhir
        assert done == [1]


class TestTweenAktif:
    def test_menjadwalkan_dan_akhirnya_mencapai_satu(self, tk_root):
        seen = []
        done = []
        motion.tween(tk_root, 60, seen.append, on_done=lambda: done.append(1),
                     easing=motion.linear)
        # pompa event loop sampai selesai (batas aman 3 detik)
        import time
        t0 = time.perf_counter()
        while not done and time.perf_counter() - t0 < 3.0:
            tk_root.update()
        assert done == [1], "tween tidak pernah selesai"
        assert seen[-1] == 1.0, "frame terakhir harus tepat 1.0"
        assert seen[0] < 1.0, "harus ada frame antara, bukan langsung selesai"
        assert all(b >= a for a, b in zip(seen, seen[1:])), "progres harus monoton"

    def test_durasi_nol_langsung_selesai(self, tk_root):
        seen = []
        motion.tween(tk_root, 0, seen.append)
        assert seen == [1.0]


class TestPembatalan:
    def test_cancel_for_menghentikan_tween_berjalan(self, tk_root):
        seen = []
        motion.tween(tk_root, 2000, seen.append)
        tk_root.update()
        motion.cancel_for(tk_root)
        n = len(seen)
        for _ in range(5):
            tk_root.update()
        assert len(seen) == n, "tween masih berjalan setelah dibatalkan"
        assert 1.0 not in seen, "tween yang dibatalkan tidak boleh memaksa frame akhir"

    def test_widget_dihancurkan_membatalkan_tween_nya(self, tk_root):
        import customtkinter as ctk
        child = ctk.CTkFrame(tk_root)
        seen = []
        motion.tween(child, 2000, seen.append)
        tk_root.update()
        child.destroy()
        tk_root.update()
        assert motion.active_count() == 0, "registry bocor setelah widget dihancurkan"

    def test_registry_bersih_setelah_tween_selesai_wajar(self, tk_root):
        import time
        done = []
        motion.tween(tk_root, 40, lambda t: None, on_done=lambda: done.append(1))
        t0 = time.perf_counter()
        while not done and time.perf_counter() - t0 < 3.0:
            tk_root.update()
        assert motion.active_count() == 0


class TestRenderSignature:
    def test_render_pertama_selalu_dianggap_berubah(self):
        sig = motion.RenderSignature()
        assert sig.changed(1, "2026-07") is True

    def test_tuple_sama_berarti_tidak_berubah(self):
        sig = motion.RenderSignature()
        sig.changed(1, "2026-07")
        assert sig.changed(1, "2026-07") is False

    def test_satu_bagian_berubah_sudah_cukup(self):
        sig = motion.RenderSignature()
        sig.changed(1, "2026-07")
        assert sig.changed(2, "2026-07") is True

    def test_kembali_ke_nilai_lama_tetap_dihitung_berubah(self):
        sig = motion.RenderSignature()
        sig.changed(1, "2026-07")
        sig.changed(1, "2026-08")
        assert sig.changed(1, "2026-07") is True

    def test_kata_pencarian_heatmap_sengaja_diluar_sidik_jari(self):
        """Regresi jebakan #1: heatmap._repaint() juga dipanggil oleh
        _on_search. Sidik jari heatmap TIDAK memuat kata pencarian, jadi
        mengetik tidak akan pernah bisa memicu sapuan ulang."""
        sig = motion.RenderSignature()
        data_version, month, sort_key = 3, "2026-07", "nama"
        assert sig.changed(data_version, month, sort_key) is True
        # user mengetik di kotak cari — tidak ada bagian sidik jari yang berubah
        assert sig.changed(data_version, month, sort_key) is False


class TestHoverJobsTidakBocor:
    """hover_tint menyimpan timer di _hover_jobs berkunci id(widget). Entri itu
    semula hanya dibuang saat animasi selesai wajar — kalau widget dihancurkan
    di tengah animasi, entrinya tertinggal selamanya. Dict-nya tumbuh sepanjang
    sesi, dan karena Python memakai ulang id() setelah GC, widget baru bisa
    mewarisi id timer milik widget yang sudah mati."""

    def test_widget_dihancurkan_membersihkan_hover_jobs(self, tk_root):
        import customtkinter as ctk
        motion._hover_jobs.clear()
        f = ctk.CTkFrame(tk_root, fg_color="#0A0A0A")
        f.pack()
        tk_root.update()
        motion.hover_tint(f, "#0A0A0A", "#1F1F1F", duration_ms=5000)
        tk_root.update()
        assert len(motion._hover_jobs) == 1, "prasyarat: tween panjang harus tercatat"
        f.destroy()
        tk_root.update()
        assert motion._hover_jobs == {}, "entri basi tertinggal setelah widget mati"
        assert motion.active_count() == 0

    def test_cancel_for_juga_membersihkan_hover_jobs(self, tk_root):
        import customtkinter as ctk
        motion._hover_jobs.clear()
        f = ctk.CTkFrame(tk_root, fg_color="#0A0A0A")
        f.pack()
        tk_root.update()
        motion.hover_tint(f, "#0A0A0A", "#1F1F1F", duration_ms=5000)
        motion.cancel_for(f)
        assert motion._hover_jobs == {}
        f.destroy()

    def test_membatalkan_satu_properti_tidak_menyentuh_properti_lain(self, tk_root):
        """Chip bulan aktif menganimasikan fg_color dan border_color sekaligus;
        keduanya harus hidup berdampingan."""
        import customtkinter as ctk
        motion._hover_jobs.clear()
        f = ctk.CTkFrame(tk_root, fg_color="#0A0A0A", border_width=1,
                         border_color="#262626")
        f.pack()
        tk_root.update()
        motion.hover_tint(f, "#0A0A0A", "#1F1F1F", duration_ms=5000)
        motion.hover_tint(f, "#262626", "#EC4899", duration_ms=5000,
                          option="border_color")
        assert len(motion._hover_jobs) == 2, "dua properti harus tercatat terpisah"
        f.destroy()
        tk_root.update()
        assert motion._hover_jobs == {}
