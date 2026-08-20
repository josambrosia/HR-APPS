"""Mesin animasi terpusat — v25 Motion Pass.

Aplikasi ini berjalan di Tk, yang tidak punya kanal alpha pada widget,
tidak punya transform, dan tidak punya compositor. Yang bisa dianimasikan
hanya: warna (interpolasi), geometri (place/coords), teks, dan alpha pada
Toplevel/root (khusus Windows).

Pengukuran yang mendasari modul ini (mesin target, median ms per frame
termasuk redraw):

    Toplevel -alpha                      0,23 ms   4365 fps
    CTkButton.configure(text)            0,36 ms   2759 fps
    Canvas coords(), 15 bar              1,74 ms    576 fps
    CTkFrame.configure(fg_color)         2,49 ms    401 fps
    Canvas sapuan bertahap per kolom     2,73 ms    366 fps
    Treeview tag_configure di-tween      9,83 ms    102 fps
    20x CTkLabel.configure(text_color)  15,73 ms     64 fps  <- terlalu berat
    675 sel Canvas dipudarkan serentak  32,54 ms     31 fps  <- terlalu berat

Aturan yang lahir dari angka itu: Canvas ~200x lebih murah per elemen
daripada widget customtkinter. Animasi yang menyentuh banyak elemen WAJIB
berjalan di Canvas; animasi widget CTk dibatasi 1-3 widget sekaligus.
"""
from __future__ import annotations


# ─────────────────────────────────────────────── interpolasi warna

def _parse_hex(value: str) -> tuple[int, int, int]:
    """'#RRGGBB' -> (r, g, b). Bentuk singkat 3-digit ditolak keras."""
    if not isinstance(value, str) or len(value) != 7 or value[0] != "#":
        raise ValueError(f"butuh warna '#RRGGBB', dapat {value!r}")
    try:
        return (int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16))
    except ValueError as exc:
        raise ValueError(f"warna tidak valid: {value!r}") from exc


def lerp_hex(start: str, end: str, t: float) -> str:
    """Interpolasi dua warna '#RRGGBB'. `t` dijepit ke 0..1."""
    t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
    a = _parse_hex(start)
    b = _parse_hex(end)
    return "#%02X%02X%02X" % tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


# ─────────────────────────────────────────────── easing

def linear(t: float) -> float:
    return t


def ease_out_cubic(t: float) -> float:
    """Cepat di awal, melambat di akhir. Default untuk gerakan masuk."""
    return 1.0 - (1.0 - t) ** 3


def ease_out_quint(t: float) -> float:
    """Lebih tegas daripada cubic — untuk gerakan yang harus terasa 'mendarat'."""
    return 1.0 - (1.0 - t) ** 5


# ─────────────────────────────────────────────── sakelar aktif/mati

SETTING_KEY = "motion_enabled"

_enabled: bool = True


def enabled() -> bool:
    return _enabled


def set_enabled(value: bool) -> None:
    """Dipakai layar Settings dan fixture test. Berlaku seketika untuk
    animasi BERIKUTNYA; tween yang sedang jalan dibiarkan selesai."""
    global _enabled
    _enabled = bool(value)


def load_enabled_from_db(conn) -> None:
    """Baca preferensi dari tabel settings. Nilai selain '0' berarti aktif,
    termasuk saat key-nya belum pernah ditulis."""
    from src.db.settings import get_setting
    set_enabled(get_setting(conn, SETTING_KEY, default="1") != "0")
