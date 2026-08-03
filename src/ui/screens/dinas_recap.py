"""Layar Rekap Dinas & Paparan — dua panel.

Kiri: tabel bulan aktif (Dinas / Paparan / Total + grand total).
Kanan: papan peringkat dengan rentang bisa diatur (3 bln / 6 bln / Tahun ini,
default Tahun ini) — garis aksen magenta memudar per peringkat, penanda 👑/💎,
bar bertumpuk teal (dinas) + ungu (paparan), kolom angka sejajar.
Cetak merender dinas_recap_print.html.j2 ke temp file lalu membukanya di
browser (Ctrl-P / Save PDF), mengikuti rentang yang aktif di layar.
Lihat docs/superpowers/specs/2026-07-30-reason-editing-dinas-paparan-recap-design.md.
"""
import os
import tempfile
from datetime import date
from pathlib import Path

import customtkinter as ctk

from src.config import DB_PATH
from src.core.dinas_recap import SPANS, DEFAULT_SPAN
from src.db.connection import get_connection
from src.db.settings import get_setting
from src.reports.dinas_recap_print import (
    build_dinas_recap_context, render_dinas_recap_html)
from src.ui.browser_launcher import open_html_in_browser
from src.ui.theme import (
    COLOR_SURFACE, COLOR_SURFACE_HIGH, COLOR_BORDER,
    COLOR_ACCENT, COLOR_ACCENT_HOVER, COLOR_SECONDARY,
    COLOR_TEXT, COLOR_TEXT_DIM, COLOR_TEXT_MUTED, COLOR_TEXT_DISABLED,
    FONT_DISPLAY, FONT_BODY_BOLD, FONT_SMALL, FONT_LABEL, FONT_MONO_SMALL,
    SPACE_XS, SPACE_SM, SPACE_MD, SPACE_LG, SPACE_XL, RADIUS_MD,
)

_TEAL = "#0D9488"          # Dinas — sama dengan STATUS_COLORS['dinas'] di core.heatmap
_BAR_TRACK = "#1F1F1F"
_BAR_H = 5
# Baris sengaja pendek & satu baris. Tinggi SELALU eksplisit + propagate off:
# CTkFrame default-nya 200x200, dan tanpa ini satu baris bisa membengkak
# sampai ratusan piksel (bug tampilan v24 pertama).
_HDR_H = 16
_ROW_H = 21
_RANK_ROW_H = 34
_NUM_W = 34
_DEPT_W = 78
# Jarak aman di kanan isi panel supaya kolom angka tidak tertutup / mepet
# scrollbar CTkScrollableFrame.
_SCROLL_PAD = 14
# Warna angka peringkat: magenta memudar sesuai tier, abu untuk sisanya.
_RANK_COLORS = {1: COLOR_ACCENT, 2: COLOR_ACCENT_HOVER, 3: "#F9A8D4"}
_RANK_ACCENTS = {1: COLOR_ACCENT, 2: "#8E2C58", 3: "#5A1E3A"}
_ACCENT_REST = "#2F2F2F"
_LABEL_TO_SPAN = {label: sid for sid, label in SPANS}


class DinasRecapScreen(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._month = self._read_active_month()
        self._span = DEFAULT_SPAN
        self._month_rows = []
        self._rank_rows = []
        self._month_totals = {"dinas": 0, "paparan": 0, "total": 0}
        self._span_label = ""

        self._build_header()
        self._build_body()
        self._load()

    # ---------- data ----------
    def _read_active_month(self) -> str:
        with get_connection(DB_PATH) as conn:
            m = get_setting(conn, "current_month", default="")
        return m or date.today().strftime("%Y-%m")

    def _load(self):
        """Baca ulang kedua panel dari DB dan render. Idempoten."""
        with get_connection(DB_PATH) as conn:
            ctx = build_dinas_recap_context(conn, self._month, self._span)
        self._month_rows = ctx["month_rows"]
        self._month_totals = ctx["month_totals"]
        self._rank_rows = ctx["rank_rows"]
        self._span_label = ctx["span_label"]
        self._month_title.configure(text=f"◆ BULAN TERPILIH · {ctx['month_label'].upper()}")
        self._month_count.configure(text=f"{len(self._month_rows)} pegawai")
        self._span_lbl.configure(text=self._span_label)
        self._render_month()
        self._render_rank()

    def on_show(self) -> None:
        """Kontrak shell: dipanggil tiap layar cache ditampilkan lagi.
        Mengikuti current_month bila berubah saat layar tersembunyi; pilihan
        rentang pengguna dipertahankan."""
        m = self._read_active_month()
        if m != self._month:
            self._month = m
        self._load()

    # ---------- build ----------
    def _build_header(self):
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=SPACE_XL, pady=(SPACE_LG, SPACE_SM))
        ctk.CTkLabel(head, text="Rekap Dinas & Paparan", font=FONT_DISPLAY,
                     text_color=COLOR_TEXT).pack(side="left")
        ctk.CTkButton(
            head, text="🖨️  Cetak", command=self._do_print, width=104,
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
            text_color="#0A0A0A", font=FONT_BODY_BOLD, corner_radius=RADIUS_MD,
        ).pack(side="right")

    def _panel(self, parent, col):
        box = ctk.CTkFrame(parent, fg_color=COLOR_SURFACE, border_width=1,
                           border_color=COLOR_BORDER, corner_radius=RADIUS_MD)
        box.grid(row=0, column=col, sticky="nsew",
                 padx=(0, SPACE_SM) if col == 0 else (SPACE_SM, 0))
        box.grid_columnconfigure(0, weight=1)
        box.grid_rowconfigure(1, weight=1)
        return box

    def _build_body(self):
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=SPACE_XL, pady=(0, SPACE_LG))
        body.grid_columnconfigure(0, weight=11, uniform="p")
        body.grid_columnconfigure(1, weight=9, uniform="p")
        body.grid_rowconfigure(0, weight=1)

        # ---- panel kiri: bulan terpilih ----
        left = self._panel(body, 0)
        lhead = ctk.CTkFrame(left, fg_color="transparent")
        lhead.grid(row=0, column=0, sticky="ew", padx=SPACE_MD, pady=(SPACE_SM, SPACE_XS))
        self._month_title = ctk.CTkLabel(lhead, text="", font=FONT_MONO_SMALL,
                                         text_color=COLOR_TEXT_DIM)
        self._month_title.pack(side="left")
        self._month_count = ctk.CTkLabel(lhead, text="", font=FONT_MONO_SMALL,
                                         text_color=COLOR_TEXT_DISABLED)
        self._month_count.pack(side="right")
        self._month_list = ctk.CTkScrollableFrame(left, fg_color="transparent")
        self._month_list.grid(row=1, column=0, sticky="nsew", padx=SPACE_SM, pady=(0, SPACE_SM))
        self._month_list.grid_columnconfigure(0, weight=1)

        # ---- panel kanan: papan peringkat ----
        right = self._panel(body, 1)
        rhead = ctk.CTkFrame(right, fg_color="transparent")
        rhead.grid(row=0, column=0, sticky="ew", padx=SPACE_MD, pady=(SPACE_SM, SPACE_XS))
        ctk.CTkLabel(rhead, text="🏆 PAPAN PERINGKAT", font=FONT_MONO_SMALL,
                     text_color=COLOR_TEXT_DIM).pack(side="left")
        self._span_ctl = ctk.CTkSegmentedButton(
            rhead, values=[label for _sid, label in SPANS],
            command=self._on_span,
            fg_color=COLOR_SURFACE_HIGH, selected_color=COLOR_ACCENT,
            selected_hover_color=COLOR_ACCENT_HOVER, unselected_color=COLOR_SURFACE_HIGH,
            unselected_hover_color=COLOR_BORDER, text_color=COLOR_TEXT,
            font=FONT_SMALL, corner_radius=RADIUS_MD)
        self._span_ctl.set(dict(SPANS)[DEFAULT_SPAN])
        self._span_ctl.pack(side="right")
        self._span_lbl = ctk.CTkLabel(right, text="", font=FONT_MONO_SMALL,
                                      text_color=COLOR_TEXT_DISABLED, anchor="w")
        self._span_lbl.grid(row=2, column=0, sticky="ew", padx=SPACE_MD, pady=(0, SPACE_SM))
        self._rank_list = ctk.CTkScrollableFrame(right, fg_color="transparent")
        self._rank_list.grid(row=1, column=0, sticky="nsew", padx=SPACE_SM, pady=(0, SPACE_XS))
        self._rank_list.grid_columnconfigure(0, weight=1)

    # ---------- render ----------
    @staticmethod
    def _clear(frame):
        for w in frame.winfo_children():
            w.destroy()

    def _num(self, parent, value, color, *, dim_zero=True):
        """Sel angka mono rata-kanan; nol diredupkan agar angka penting menonjol."""
        return ctk.CTkLabel(
            parent, text=str(value), font=FONT_MONO_SMALL, width=_NUM_W, anchor="e",
            text_color=(COLOR_TEXT_DISABLED if (dim_zero and not value) else color))

    def _line(self, parent, height, *, scroll_pad=False):
        """Baris berketinggian tetap — propagate dimatikan supaya ukuran default
        CTkFrame (200px) tidak pernah menaikkan tinggi baris.

        scroll_pad=True menyisakan ruang di kanan agar isi tidak mepet scrollbar
        (dipakai untuk baris yang menempel langsung pada CTkScrollableFrame)."""
        f = ctk.CTkFrame(parent, fg_color="transparent", height=height)
        f.pack(fill="x", padx=(0, _SCROLL_PAD) if scroll_pad else 0)
        f.pack_propagate(False)
        return f

    def _empty(self, parent, text):
        ctk.CTkLabel(parent, text=text, font=FONT_SMALL,
                     text_color=COLOR_TEXT_MUTED).pack(pady=SPACE_LG)

    def _render_month(self):
        self._clear(self._month_list)
        if not self._month_rows:
            self._empty(self._month_list, "Belum ada pegawai aktif.")
            return
        hdr = self._line(self._month_list, _HDR_H, scroll_pad=True)
        ctk.CTkLabel(hdr, text="NAMA", font=FONT_LABEL, text_color=COLOR_TEXT_DISABLED,
                     anchor="w").pack(side="left", fill="x", expand=True)
        for cap, col in (("TOT", COLOR_TEXT_DIM), ("PAP", COLOR_SECONDARY),
                         ("DIN", _TEAL)):
            ctk.CTkLabel(hdr, text=cap, font=FONT_LABEL, text_color=col,
                         width=_NUM_W, anchor="e").pack(side="right")

        for r in self._month_rows:
            row = self._line(self._month_list, _ROW_H, scroll_pad=True)
            self._num(row, r["total"], COLOR_TEXT).pack(side="right")
            self._num(row, r["paparan"], COLOR_SECONDARY).pack(side="right")
            self._num(row, r["dinas"], _TEAL).pack(side="right")
            # Nama + dept menempel jadi satu blok; dept dibiarkan meredup agar
            # tidak menyaingi nama dan tidak meninggalkan celah kosong lebar.
            who = ctk.CTkFrame(row, fg_color="transparent")
            who.pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(who, text=r["nama"], font=FONT_SMALL, text_color=COLOR_TEXT,
                         anchor="w").pack(side="left")
            if r["dept"]:
                ctk.CTkLabel(who, text=f"· {r['dept']}", font=FONT_MONO_SMALL,
                             text_color=COLOR_TEXT_DISABLED,
                             anchor="w").pack(side="left", padx=(SPACE_SM, 0))

        ctk.CTkFrame(self._month_list, fg_color=COLOR_BORDER, height=1).pack(
            fill="x", padx=(0, _SCROLL_PAD), pady=SPACE_XS)
        tot = self._line(self._month_list, _ROW_H, scroll_pad=True)
        ctk.CTkLabel(tot, text="TOTAL", font=FONT_LABEL, text_color=COLOR_TEXT,
                     anchor="w").pack(side="left", fill="x", expand=True)
        self._num(tot, self._month_totals["total"], COLOR_TEXT, dim_zero=False).pack(side="right")
        self._num(tot, self._month_totals["paparan"], COLOR_SECONDARY, dim_zero=False).pack(side="right")
        self._num(tot, self._month_totals["dinas"], _TEAL, dim_zero=False).pack(side="right")

    def _render_rank(self):
        self._clear(self._rank_list)
        if not self._rank_rows:
            self._empty(self._rank_list, "Belum ada pegawai aktif.")
            return
        for r in self._rank_rows:
            ranked = r["total"] > 0          # nol tidak diberi warna tier
            wrap = ctk.CTkFrame(self._rank_list, fg_color="transparent",
                                height=_RANK_ROW_H)
            wrap.pack(fill="x", padx=(0, _SCROLL_PAD))
            wrap.pack_propagate(False)
            # Garis aksen tier di kiri (pilihan desain user — lihat spec §4.4).
            # Tinggi eksplisit, BUKAN fill="y": fill akan mengunci diri ke tinggi
            # default CTkFrame (200px) dan meregangkan seluruh baris.
            ctk.CTkFrame(
                wrap, width=3, height=_RANK_ROW_H - 8, corner_radius=2,
                fg_color=(_RANK_ACCENTS.get(r["rank"], _ACCENT_REST)
                          if ranked else _ACCENT_REST),
            ).pack(side="left", padx=(0, SPACE_SM))
            ctk.CTkLabel(
                wrap, text=str(r["rank"]), font=FONT_MONO_SMALL, width=14, anchor="e",
                text_color=(_RANK_COLORS.get(r["rank"], COLOR_TEXT_MUTED)
                            if ranked else COLOR_TEXT_DISABLED),
            ).pack(side="left")

            body = ctk.CTkFrame(wrap, fg_color="transparent")
            body.pack(side="left", fill="both", expand=True, padx=(SPACE_SM, 0))
            line = self._line(body, _ROW_H)
            ctk.CTkLabel(line, text=f"{r['nama']} {r['mark']}".strip(), font=FONT_SMALL,
                         text_color=(COLOR_TEXT if ranked else COLOR_TEXT_MUTED),
                         anchor="w").pack(side="left", fill="x", expand=True)
            self._num(line, r["total"], COLOR_TEXT).pack(side="right")
            self._num(line, r["paparan"], COLOR_SECONDARY).pack(side="right")
            self._num(line, r["dinas"], _TEAL).pack(side="right")
            self._bar(body, r)

    def _bar(self, parent, r):
        """Bar bertumpuk: panjang ∝ total relatif pemuncak, isi = komposisi."""
        track = ctk.CTkFrame(parent, fg_color=_BAR_TRACK, height=_BAR_H,
                             corner_radius=2)
        track.pack(fill="x")
        track.pack_propagate(False)
        if not r["total"]:
            return          # tanpa tugas: hanya rel kosong
        fill = ctk.CTkFrame(track, fg_color="transparent")
        fill.place(relx=0, rely=0, relwidth=max(r["bar_pct"], 1) / 100, relheight=1)
        if r["dinas_pct"]:
            ctk.CTkFrame(fill, fg_color=_TEAL, corner_radius=2).place(
                relx=0, rely=0, relwidth=r["dinas_pct"] / 100, relheight=1)
        if r["paparan_pct"]:
            ctk.CTkFrame(fill, fg_color=COLOR_SECONDARY, corner_radius=2).place(
                relx=r["dinas_pct"] / 100, rely=0,
                relwidth=r["paparan_pct"] / 100, relheight=1)

    # ---------- events ----------
    def _on_span(self, label):
        self._span = _LABEL_TO_SPAN.get(label, DEFAULT_SPAN)
        self._load()

    def _do_print(self):
        with get_connection(DB_PATH) as conn:
            html = render_dinas_recap_html(conn, self._month, self._span)
        fd, path = tempfile.mkstemp(suffix=".html", prefix="rekap_dinas_")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(html)
        open_html_in_browser(Path(path))
