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
    key = id(widget)
    for job_id in _jobs.pop(key, set()):
        try:
            widget.after_cancel(job_id)
        except tk.TclError:
            # Widget sudah lenyap bersama seluruh timernya. Ini satu-satunya
            # pengecualian yang ditangkap di jalur ini — JANGAN dilebarkan jadi
            # `except Exception`. Di v24 penangkap selebar itu menyembunyikan
            # tabrakan nama _draw pada CTkFrame selama berjam-jam.
            pass
    # Indeks per-properti milik hover_tint ikut dibersihkan. Tanpa ini entrinya
    # tertinggal saat widget dihancurkan di tengah animasi: dict tumbuh sepanjang
    # sesi, dan karena Python memakai ulang id() setelah GC, widget baru bisa
    # mewarisi id timer milik widget yang sudah mati.
    for hover_key in [k for k in _hover_jobs if k[0] == key]:
        _hover_jobs.pop(hover_key, None)


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


# ─────────────────────────────────────────────── penolong: pil geser

def slide_pill(pill, target_widget, duration_ms: int = None) -> None:
    """Geser + ubah lebar `pill` supaya menutupi `target_widget`.

    Posisi dan lebar DIUKUR dari widget tujuan (`winfo_x`/`winfo_width`),
    tidak diasumsikan: WeekNavBar kebetulan seragam 175px, tapi segmented
    button Rekap Dinas lebarnya 53/53/85.

    `pill` WAJIB `tk.Frame`, bukan `CTkFrame` — CTkFrame menskalakan koordinat
    di place() tapi tidak di place_configure(), sehingga penempatan pertama
    meleset di layar ber-DPI tinggi (lihat item 02).
    """
    from src.ui.theme import MOTION_BASE
    if duration_ms is None:
        duration_ms = MOTION_BASE
    target_widget.update_idletasks()
    to_x, to_w = target_widget.winfo_x(), target_widget.winfo_width()
    to_y, to_h = target_widget.winfo_y(), target_widget.winfo_height()

    if not pill.winfo_ismapped():
        # Penempatan pertama: langsung, tanpa meluncur dari posisi nol.
        pill.place(x=to_x, y=to_y, width=to_w, height=to_h)
        pill.lower(target_widget)
        return

    cancel_for(pill)
    from_x, from_w = pill.winfo_x(), pill.winfo_width()
    tween(pill, duration_ms,
          lambda t: pill.place_configure(
              x=int(from_x + (to_x - from_x) * t),
              width=int(from_w + (to_w - from_w) * t),
              y=to_y, height=to_h),
          on_done=lambda: pill.place_configure(x=to_x, y=to_y,
                                               width=to_w, height=to_h))


# ─────────────────────────────────────────────── penolong: hitung-naik

def count_up(label, to_value: int, fmt: Callable[[int], str] = str,
             duration_ms: int = None) -> None:
    """Naikkan teks angka sebuah label dari 0 ke `to_value`.

    Hanya mengganti teks — 0,36 ms per frame, salah satu yang termurah.
    Selalu mendarat tepat di `to_value`, tidak pernah di angka pembulatan.
    """
    from src.ui.theme import MOTION_SLOW
    if duration_ms is None:
        duration_ms = MOTION_SLOW
    cancel_for(label)
    tween(label, duration_ms,
          lambda t: label.configure(text=fmt(int(round(to_value * t)))))


# ─────────────────────────────────────────────── penolong: sapuan Canvas

def wipe_canvas(canvas, tag: str, base_color: str,
                step_ms: int = None, group_px: int = 14) -> None:
    """Nyalakan item ber-`tag` kolom demi kolom, dari kiri ke kanan.

    Kenapa bertahap dan bukan memudarkan semuanya serentak: memudarkan 675
    sel sekaligus hanya dapat 31 fps (32,54 ms per frame) — patah-patah.
    Menyapu per kolom hanya menyentuh belasan item per frame: 366 fps, dan
    seluruh sapuan tuntas dalam ~135 ms. Versi yang lebih indah kebetulan
    juga versi yang lebih cepat.

    Warna tujuan dibaca dari item itu sendiri, jadi pemanggil tidak perlu
    tahu apa pun soal palet — dan `_paint_grid` tidak perlu diubah.
    """
    from src.ui.theme import MOTION_WIPE_STEP
    if step_ms is None:
        step_ms = MOTION_WIPE_STEP

    items = canvas.find_withtag(tag)
    if not items:
        return

    targets = [(canvas.coords(i)[0], i, canvas.itemcget(i, "fill")) for i in items]

    if not _enabled:
        return                      # warnanya memang sudah benar; tak ada yang perlu dilakukan

    columns: dict[int, list] = {}
    for x, item, fill in targets:
        columns.setdefault(int(x // group_px), []).append((item, fill))

    for item, _fill in [(i, f) for col in columns.values() for i, f in col]:
        canvas.itemconfig(item, fill=base_color)

    order = sorted(columns)
    for n, key in enumerate(order):
        def light(col=columns[key]):
            for item, fill in col:
                try:
                    canvas.itemconfig(item, fill=fill)
                except tk.TclError:
                    return          # canvas dibersihkan di tengah sapuan
        job = canvas.after(n * step_ms, light)
        _register(canvas, job)


# ─────────────────────────────────────────────── penolong: bar Canvas

def grow_bar(bar_canvas, to_pct: float, duration_ms: int = None) -> None:
    """Tumbuhkan bar metrik Rekap Dinas dari 0 ke `to_pct`.

    Bar-nya Canvas yang menggambar dari atribut `_pct`, jadi menumbuhkannya
    hanya soal men-tween satu angka lalu menggambar ulang — 1,74 ms per frame
    untuk 15 bar sekaligus.
    """
    from src.ui.theme import MOTION_SLOW
    from src.ui.screens.dinas_recap import _draw_metric_bar
    if duration_ms is None:
        duration_ms = MOTION_SLOW
    cancel_for(bar_canvas)

    def frame(t):
        bar_canvas._pct = to_pct * t
        _draw_metric_bar(bar_canvas)

    tween(bar_canvas, duration_ms, frame,
          on_done=lambda: (setattr(bar_canvas, "_pct", to_pct),
                           _draw_metric_bar(bar_canvas)))


# ─────────────────────────────────────────────── penolong: fade jendela

def fade_window(window, duration_ms: int = None) -> None:
    """Munculkan Toplevel/root dengan memudar dari transparan ke penuh.

    Widget Tk tidak punya kanal alpha, tapi JENDELA punya — di Windows.
    Ini satu-satunya tempat di seluruh aplikasi yang bisa memudar sungguhan,
    dan biayanya praktis nol (0,23 ms per frame).

    Kalau platform tidak mendukung -alpha, jendela tetap tampil penuh:
    tanpa fade lebih baik daripada tanpa jendela.
    """
    from src.ui.theme import MOTION_FADE
    if duration_ms is None:
        duration_ms = MOTION_FADE

    def _set(value: float) -> bool:
        try:
            window.attributes("-alpha", value)
            return True
        except tk.TclError:
            return False

    if not _set(0.0):
        _set(1.0)
        return
    tween(window, duration_ms, lambda t: _set(t), on_done=lambda: _set(1.0),
          easing=linear)
