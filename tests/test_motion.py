"""Mesin animasi v25 — fungsi murni, tween, registry pembatalan."""
import pytest

from src.ui import motion


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
