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

import time
import tkinter as tk
from typing import Callable, Optional


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


# ─────────────────────────────────────────────── registry tween aktif

# key = id(widget) -> set[after_id]. Dipakai untuk membatalkan seluruh
# animasi milik satu widget saat widget itu dihancurkan.
_jobs: dict[int, set[str]] = {}
# widget yang sudah dipasangi binding <Destroy>, supaya tidak dipasang dua kali
_bound: set[int] = set()

_FRAME_MS = 16          # ~60 fps; jam dinding yang menentukan, ini hanya laju polling


def active_count() -> int:
    """Jumlah tween yang sedang berjalan. Untuk tes kebocoran registry."""
    return sum(len(s) for s in _jobs.values())


def _register(widget, job_id: str) -> None:
    key = id(widget)
    _jobs.setdefault(key, set()).add(job_id)
    if key not in _bound:
        _bound.add(key)
        widget.bind("<Destroy>", lambda _e, w=widget: _on_destroy(w), add="+")


def _forget(widget, job_id: str) -> None:
    jobs = _jobs.get(id(widget))
    if jobs is not None:
        jobs.discard(job_id)
        if not jobs:
            _jobs.pop(id(widget), None)


def _on_destroy(widget) -> None:
    cancel_for(widget)
    _bound.discard(id(widget))


def cancel_for(widget) -> None:
    """Batalkan seluruh tween milik `widget`. Frame akhir TIDAK dipaksakan —
    pembatalan berarti berhenti di tempat, bukan melompat ke ujung."""
    for job_id in _jobs.pop(id(widget), set()):
        try:
            widget.after_cancel(job_id)
        except tk.TclError:
            # Widget sudah lenyap bersama seluruh timernya. Ini satu-satunya
            # pengecualian yang ditangkap di jalur ini — JANGAN dilebarkan jadi
            # `except Exception`. Di v24 penangkap selebar itu menyembunyikan
            # tabrakan nama _draw pada CTkFrame selama berjam-jam.
            pass


# ─────────────────────────────────────────────── tween

def tween(
    widget,
    duration_ms: int,
    on_frame: Callable[[float], None],
    on_done: Optional[Callable[[], None]] = None,
    easing: Callable[[float], float] = ease_out_cubic,
) -> Optional[str]:
    """Animasikan `on_frame(t)` dari 0 ke 1 selama `duration_ms`.

    `t` sudah melewati `easing`. Frame terakhir dijamin tepat 1.0, sehingga
    keadaan akhir tidak pernah bergantung pada waktu kedatangan frame.

    Saat motion mati (atau durasi <= 0): tidak ada timer sama sekali —
    `on_frame(1.0)` lalu `on_done()` dipanggil langsung. Ini yang membuat
    setiap pemanggil bisa ditulis tanpa percabangan, dan yang membuat
    keadaan akhir identik dengan v24.

    Mengembalikan id timer pertama, atau None bila berjalan seketika.
    """
    if not _enabled or duration_ms <= 0:
        on_frame(1.0)
        if on_done is not None:
            on_done()
        return None

    start = time.perf_counter()
    holder: dict[str, Optional[str]] = {"job": None}

    def step() -> None:
        if holder["job"] is not None:
            _forget(widget, holder["job"])
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        raw = elapsed_ms / duration_ms
        if raw >= 1.0:
            on_frame(1.0)
            if on_done is not None:
                on_done()
            return
        on_frame(easing(raw))
        job = widget.after(_FRAME_MS, step)
        holder["job"] = job
        _register(widget, job)

    first = widget.after(_FRAME_MS, step)
    holder["job"] = first
    _register(widget, first)
    return first


# ─────────────────────────────────────────────── kapan boleh main ulang

_UNSET = object()


class RenderSignature:
    """Menjawab satu pertanyaan: 'apakah yang tampil sekarang berbeda dari
    render sebelumnya?'

    Sejak v22 layar disimpan di cache (app.py._show + kontrak on_show), jadi
    tanpa aturan setiap animasi masuk akan main ulang tiap kali user bolak-
    balik menu. Setelah kesepuluh kalinya, 'hidup' berubah jadi 'mengganggu'.

    Apa yang TIDAK dimasukkan ke sidik jari sama pentingnya dengan apa yang
    dimasukkan. Heatmap sengaja tidak memasukkan kata pencarian dan ukuran
    jendela, sehingga mengetik atau resize tidak pernah bisa memicu sapuan —
    bukan karena ada `if` yang mencegah, tapi karena menurut definisinya
    tidak ada yang berubah.
    """

    __slots__ = ("_last",)

    def __init__(self):
        self._last = _UNSET

    def changed(self, *parts) -> bool:
        if self._last is _UNSET or self._last != parts:
            self._last = parts
            return True
        return False

    def reset(self) -> None:
        """Paksa render berikutnya dianggap berubah."""
        self._last = _UNSET


# ─────────────────────────────────────────────── penolong: hover

_hover_jobs: dict[tuple[int, str], str] = {}


def hover_tint(widget, from_color: str, to_color: str,
               duration_ms: int = None, option: str = "fg_color") -> None:
    """Alirkan satu properti warna widget dari `from_color` ke `to_color`.

    Dipakai untuk hover 1-3 widget sekaligus. JANGAN dipakai untuk puluhan
    widget serentak — 20 CTkLabel hanya dapat 64 fps (lihat docstring modul).

    Tween lama pada (widget, properti) YANG SAMA dibatalkan lebih dulu supaya
    masuk-keluar kursor cepat tidak menumpuk dua animasi yang saling melawan.
    Properti berbeda pada widget yang sama berjalan berdampingan.
    """
    from src.ui.theme import MOTION_FAST
    if duration_ms is None:
        duration_ms = MOTION_FAST
    key = (id(widget), option)
    old = _hover_jobs.pop(key, None)
    if old is not None:
        try:
            widget.after_cancel(old)
        except tk.TclError:
            pass
        _forget(widget, old)
    job = tween(widget, duration_ms,
                lambda t: widget.configure(**{option: lerp_hex(from_color, to_color, t)}),
                on_done=lambda: _hover_jobs.pop(key, None))
    if job is not None:
        _hover_jobs[key] = job


# ─────────────────────────────────────────────── penolong: indikator meluncur

def slide_to_y(widget, from_y: int, to_y: int, duration_ms: int = None) -> None:
    """Geser widget ber-`place()` secara vertikal dari `from_y` ke `to_y`.

    Widget WAJIB sudah diposisikan dengan place(); pack/grid tidak bisa
    dianimasikan tanpa menata ulang tata letak tiap frame.
    """
    from src.ui.theme import MOTION_BASE
    if duration_ms is None:
        duration_ms = MOTION_BASE
    cancel_for(widget)
    tween(widget, duration_ms,
          lambda t: widget.place_configure(y=int(from_y + (to_y - from_y) * t)))
