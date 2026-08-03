"""Overlay "Memuat…" yang menutupi area konten selama layar disiapkan.

Dipakai shell (src/ui/app.py) saat berpindah ke layar yang memang berat —
kunjungan pertama ke Dashboard/Heatmap/Rekap Dinas/Outlier bisa menahan UI
1–4 detik sementara ratusan widget dibangun.

Kejujuran teknis: Tk membangun DAN menggambar pada thread yang sama, jadi
cincin ini TIDAK bisa berputar selama pembangunan widget berlangsung —
tidak ada pustaka UI Tk yang bisa. Yang dijamin komponen ini: overlay
tampil dan tergambar SEBELUM pekerjaan berat dimulai (show() memaksa satu
kali repaint), sehingga jendela tidak pernah terlihat mati/menggantung
tanpa penjelasan. Cincin berputar di sela-sela saat main loop bebas.
"""
import tkinter as tk

import customtkinter as ctk

from src.ui.theme import (
    COLOR_BG, COLOR_SURFACE, COLOR_BORDER, COLOR_ACCENT,
    COLOR_TEXT, COLOR_TEXT_MUTED,
    FONT_BODY_BOLD, FONT_MONO_SMALL,
    SPACE_SM, SPACE_MD, SPACE_LG, SPACE_XL, RADIUS_LG,
)

_RING = 42          # sisi kanvas cincin (px)
_THICK = 3          # tebal goresan cincin
_SWEEP = 95         # panjang busur aksen (derajat)
_STEP = 18          # derajat per bingkai
_FRAME_MS = 40      # jeda antar bingkai


class LoadingOverlay(ctk.CTkFrame):
    """Panel penuh berisi kartu 'Memuat…'. Pakai show() lalu hide()."""

    def __init__(self, parent, text: str = "Memuat data…", detail: str = ""):
        super().__init__(parent, fg_color=COLOR_BG)
        self._angle = 0
        self._job = None

        card = ctk.CTkFrame(self, fg_color=COLOR_SURFACE, border_width=1,
                            border_color=COLOR_BORDER, corner_radius=RADIUS_LG)
        card.place(relx=0.5, rely=0.5, anchor="center")

        self._canvas = tk.Canvas(card, width=_RING, height=_RING,
                                 bg=COLOR_SURFACE, highlightthickness=0, bd=0)
        self._canvas.pack(padx=SPACE_XL * 2, pady=(SPACE_LG, SPACE_MD))

        self._label = ctk.CTkLabel(card, text=text, font=FONT_BODY_BOLD,
                                   text_color=COLOR_TEXT)
        self._label.pack(padx=SPACE_XL * 2, pady=(0, SPACE_SM if detail else SPACE_LG))

        self._detail = None
        if detail:
            self._detail = ctk.CTkLabel(card, text=detail, font=FONT_MONO_SMALL,
                                        text_color=COLOR_TEXT_MUTED)
            self._detail.pack(padx=SPACE_XL * 2, pady=(0, SPACE_LG))

        self._draw_ring()

    # ---------- gambar ----------
    # JANGAN menamainya _draw(): CTkFrame punya _draw(no_color_updates=...)
    # internal sendiri dan menimpanya membuat konstruktor CTk meledak.
    def _draw_ring(self):
        c = self._canvas
        c.delete("all")
        pad = _THICK
        box = (pad, pad, _RING - pad, _RING - pad)
        # rel penuh, lalu busur aksen yang berputar
        c.create_oval(*box, outline=COLOR_BORDER, width=_THICK)
        c.create_arc(*box, start=self._angle, extent=_SWEEP, style="arc",
                     outline=COLOR_ACCENT, width=_THICK)

    def _tick(self):
        self._angle = (self._angle - _STEP) % 360
        self._draw_ring()
        try:
            self._job = self.after(_FRAME_MS, self._tick)
        except tk.TclError:
            self._job = None        # widget sudah dibuang

    # ---------- daur hidup ----------
    def show(self):
        """Tampilkan menutupi induk DAN paksa tergambar sekarang juga.

        update_idletasks() (bukan update()) sengaja dipakai: cukup untuk
        melukis, tanpa memproses ulang antrean event — jadi tidak ada
        re-entrancy ke penangan yang sedang berjalan."""
        self.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.lift()
        try:
            self.update_idletasks()
        except tk.TclError:
            pass
        self._job = self.after(_FRAME_MS, self._tick)
        return self

    def set_text(self, text: str):
        self._label.configure(text=text)

    def hide(self):
        """Hentikan animasi lalu buang overlay. Aman dipanggil dua kali."""
        if self._job is not None:
            try:
                self.after_cancel(self._job)
            except tk.TclError:
                pass
            self._job = None
        try:
            self.place_forget()
            self.destroy()
        except tk.TclError:
            pass
