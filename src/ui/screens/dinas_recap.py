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
    FONT_DISPLAY, FONT_BODY, FONT_BODY_BOLD, FONT_SMALL, FONT_LABEL,
    FONT_MONO_DATA, FONT_MONO_SMALL,
    SPACE_XS, SPACE_SM, SPACE_MD, SPACE_LG, SPACE_XL, RADIUS_MD,
)

_TEAL = "#0D9488"          # Dinas — sama dengan STATUS_COLORS['dinas'] di core.heatmap
_BAR_TRACK = "#1F1F1F"
_BAR_H = 6
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

    def _num(self, parent, text, color, width):
        return ctk.CTkLabel(parent, text=str(text), font=FONT_MONO_DATA,
                            text_color=color, width=width, anchor="e")

    def _render_month(self):
        self._clear(self._month_list)
        if not self._month_rows:
            ctk.CTkLabel(self._month_list, text="Belum ada dinas atau paparan bulan ini.",
                         font=FONT_SMALL, text_color=COLOR_TEXT_MUTED).pack(pady=SPACE_LG)
            return
        hdr = ctk.CTkFrame(self._month_list, fg_color="transparent")
        hdr.pack(fill="x", pady=(0, SPACE_XS))
        ctk.CTkLabel(hdr, text="NAMA", font=FONT_LABEL, text_color=COLOR_TEXT_DISABLED,
                     anchor="w").pack(side="left", fill="x", expand=True)
        for cap, col in (("DIN", _TEAL), ("PAP", COLOR_SECONDARY), ("TOT", COLOR_TEXT_DIM)):
            ctk.CTkLabel(hdr, text=cap, font=FONT_LABEL, text_color=col,
                         width=38, anchor="e").pack(side="left")
        for r in self._month_rows:
            row = ctk.CTkFrame(self._month_list, fg_color="transparent")
            row.pack(fill="x", pady=1)
            name = ctk.CTkFrame(row, fg_color="transparent")
            name.pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(name, text=r["nama"], font=FONT_BODY,
                         text_color=COLOR_TEXT, anchor="w").pack(anchor="w")
            if r["dept"]:
                ctk.CTkLabel(name, text=r["dept"], font=FONT_MONO_SMALL,
                             text_color=COLOR_TEXT_DISABLED, anchor="w").pack(anchor="w")
            self._num(row, r["dinas"],
                      _TEAL if r["dinas"] else COLOR_TEXT_DISABLED, 38).pack(side="left")
            self._num(row, r["paparan"],
                      COLOR_SECONDARY if r["paparan"] else COLOR_TEXT_DISABLED, 38).pack(side="left")
            self._num(row, r["total"], COLOR_TEXT, 38).pack(side="left")
        sep = ctk.CTkFrame(self._month_list, fg_color=COLOR_BORDER, height=1)
        sep.pack(fill="x", pady=(SPACE_XS, SPACE_XS))
        tot = ctk.CTkFrame(self._month_list, fg_color="transparent")
        tot.pack(fill="x")
        ctk.CTkLabel(tot, text="TOTAL", font=FONT_BODY_BOLD, text_color=COLOR_TEXT,
                     anchor="w").pack(side="left", fill="x", expand=True)
        self._num(tot, self._month_totals["dinas"], _TEAL, 38).pack(side="left")
        self._num(tot, self._month_totals["paparan"], COLOR_SECONDARY, 38).pack(side="left")
        self._num(tot, self._month_totals["total"], COLOR_TEXT, 38).pack(side="left")

    def _render_rank(self):
        self._clear(self._rank_list)
        if not self._rank_rows:
            ctk.CTkLabel(self._rank_list, text="Belum ada data pada rentang ini.",
                         font=FONT_SMALL, text_color=COLOR_TEXT_MUTED).pack(pady=SPACE_LG)
            return
        for r in self._rank_rows:
            accent = _RANK_ACCENTS.get(r["rank"], _ACCENT_REST)
            wrap = ctk.CTkFrame(self._rank_list, fg_color="transparent")
            wrap.pack(fill="x", pady=3)
            # garis aksen tier di kiri (pilihan desain user — lihat spec §4.4)
            ctk.CTkFrame(wrap, fg_color=accent, width=3, corner_radius=2).pack(
                side="left", fill="y", padx=(0, SPACE_SM))
            ctk.CTkLabel(wrap, text=str(r["rank"]), font=FONT_BODY_BOLD, width=18,
                         text_color=_RANK_COLORS.get(r["rank"], COLOR_TEXT_MUTED)).pack(side="left")
            body = ctk.CTkFrame(wrap, fg_color="transparent")
            body.pack(side="left", fill="x", expand=True, padx=(SPACE_XS, 0))
            line = ctk.CTkFrame(body, fg_color="transparent")
            line.pack(fill="x")
            label = f"{r['nama']} {r['mark']}".strip()
            ctk.CTkLabel(line, text=label, font=FONT_BODY, text_color=COLOR_TEXT,
                         anchor="w").pack(side="left", fill="x", expand=True)
            self._num(line, r["total"], COLOR_TEXT, 34).pack(side="right")
            self._num(line, r["paparan"], COLOR_SECONDARY, 30).pack(side="right")
            self._num(line, r["dinas"], _TEAL, 30).pack(side="right")
            self._bar(body, r)

    def _bar(self, parent, r):
        """Bar bertumpuk: panjang ∝ total relatif pemuncak, isi = komposisi."""
        track = ctk.CTkFrame(parent, fg_color=_BAR_TRACK, height=_BAR_H,
                             corner_radius=3)
        track.pack(fill="x", pady=(3, 0))
        track.pack_propagate(False)
        fill = ctk.CTkFrame(track, fg_color="transparent")
        fill.place(relx=0, rely=0, relwidth=max(r["bar_pct"], 1) / 100, relheight=1)
        if r["dinas_pct"]:
            ctk.CTkFrame(fill, fg_color=_TEAL, corner_radius=3).place(
                relx=0, rely=0, relwidth=r["dinas_pct"] / 100, relheight=1)
        if r["paparan_pct"]:
            ctk.CTkFrame(fill, fg_color=COLOR_SECONDARY, corner_radius=3).place(
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
