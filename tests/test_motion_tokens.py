"""Token durasi gerak — dipusatkan supaya rasa aplikasi bisa disetel di satu tempat."""
from src.ui import theme


def test_semua_token_gerak_ada_dan_masuk_akal():
    for name in ("MOTION_FAST", "MOTION_BASE", "MOTION_SLOW",
                 "MOTION_FLASH", "MOTION_FADE", "MOTION_WIPE_STEP"):
        val = getattr(theme, name)
        assert isinstance(val, int), f"{name} harus int"
        assert 0 < val <= 1000, f"{name} di luar rentang wajar: {val}"


def test_urutan_durasi_konsisten():
    assert theme.MOTION_FAST < theme.MOTION_BASE < theme.MOTION_SLOW
    assert theme.MOTION_SLOW < theme.MOTION_FLASH


def test_langkah_sapuan_cukup_kecil_untuk_terasa_menyapu():
    """31 kolom x MOTION_WIPE_STEP harus selesai di bawah 200 ms, sesuai
    hasil ukur 135 ms. Lebih lambat dari itu terasa seret."""
    assert 31 * theme.MOTION_WIPE_STEP < 200
