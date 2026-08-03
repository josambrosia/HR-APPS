"""Layar Rekap Dinas & Paparan — dua panel.

Kiri: tabel bulan aktif (Dinas / Paparan / Total + grand total).
Kanan: papan peringkat dengan rentang bisa diatur (3 bln / 6 bln / Tahun ini,
default Tahun ini) — garis aksen magenta memudar per peringkat, penanda 👑/💎,
bar bertumpuk teal (dinas) + ungu (paparan), kolom angka sejajar.

Performa (v24): baris TIDAK dibangun ulang saat data berganti. Widget dikumpulkan
dalam pool dan diperbarui lewat configure(); baris berlebih di-grid_remove() agar
posisinya kembali utuh saat dipakai lagi. Bar komposisi digambar pada SATU
tk.Canvas per baris, bukan empat frame bersarang. Mengganti rentang hanya memuat
ulang panel kanan — panel bulan tidak tersentuh. Sebelum ini satu pergantian
menghancurkan lalu membangun ±660 widget CustomTkinter (±9 detik pada 33 pegawai;
query-nya sendiri hanya 2 ms).

Cetak merender dinas_recap_print.html.j2 ke temp file lalu membukanya di browser
(Ctrl-P / Save PDF), mengikuti rentang yang aktif di layar.
Lihat docs/superpowers/specs/2026-07-30-reason-editing-dinas-paparan-recap-design.md.
"""
import os
import tempfile
import tkinter as tk
from datetime import date
from pathlib import Path

import customtkinter as ctk

from src.config import DB_PATH
from src.core.dinas_recap import (
    SPANS, DEFAULT_SPAN, decorate_ranks, resolve_range, span_label)
from src.core.week_utils import MONTH_NAMES_ID, full_month_range
from src.db.attendance import count_dinas_paparan_by_employee
from src.db.connection import get_connection
from src.db.settings import get_setting
from src.reports.dinas_recap_print import render_dinas_recap_html
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
        self._month_pool = []
        self._rank_pool = []

        self._build_header()
        self._build_body()
        self._load()

    # ---------- data ----------
    def _read_active_month(self) -> str:
        with get_connection(DB_PATH) as conn:
            m = get_setting(conn, "current_month", default="")
        return m or date.today().strftime("%Y-%m")

    def _month_label(self) -> str:
        y, m = int(self._month[:4]), int(self._month[5:7])
        return f"{MONTH_NAMES_ID[m]} {y}"

    def _load_month(self):
        """Panel kiri saja — tidak bergantung pada rentang peringkat."""
        start, end = full_month_range(self._month)
        with get_connection(DB_PATH) as conn:
            self._month_rows = count_dinas_paparan_by_employee(conn, start, end)
        self._month_totals = {
            "dinas": sum(r["dinas"] for r in self._month_rows),
            "paparan": sum(r["paparan"] for r in self._month_rows),
            "total": sum(r["total"] for r in self._month_rows),
        }
        self._month_title.configure(
            text=f"◆ BULAN TERPILIH · {self._month_label().upper()}")
        self._month_count.configure(text=f"{len(self._month_rows)} pegawai")
        self._render_month()

    def _load_rank(self):
        """Panel kanan saja — inilah satu-satunya yang berubah saat ganti rentang."""
        start, end = resolve_range(self._month, self._span)
        with get_connection(DB_PATH) as conn:
            self._rank_rows = decorate_ranks(
                count_dinas_paparan_by_employee(conn, start, end))
        self._span_label = span_label(self._month, self._span)
        self._span_lbl.configure(text=self._span_label)
        self._render_rank()

    def _load(self):
        self._load_month()
        self._load_rank()

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
        self._build_month_chrome()

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
        self._build_rank_chrome()

    # ---------- chrome (dibangun sekali) ----------
    def _fixed_row(self, parent, height, *, scroll_pad=True):
        f = ctk.CTkFrame(parent, fg_color="transparent", height=height)
        f.pack(fill="x", padx=(0, _SCROLL_PAD) if scroll_pad else 0)
        f.pack_propagate(False)
        return f

    def _num_label(self, parent, color=COLOR_TEXT):
        return ctk.CTkLabel(parent, text="", font=FONT_MONO_SMALL, width=_NUM_W,
                            anchor="e", text_color=color)

    @staticmethod
    def _set_num(label, value, color, *, dim_zero=True):
        label.configure(
            text=str(value),
            text_color=(COLOR_TEXT_DISABLED if (dim_zero and not value) else color))

    def _build_month_chrome(self):
        # Seluruh isi panel hidup dalam SATU container yang di-pack sekali, jadi
        # urutan header → baris → pemisah → TOTAL terkunci saat dibangun.
        # pack() pada widget yang sudah dikelola tidak memindahkan posisinya,
        # sehingga menyembunyikan lalu memunculkan bagian satu per satu pernah
        # melempar pemisah ke bawah baris TOTAL.
        self._month_body = ctk.CTkFrame(self._month_list, fg_color="transparent")
        self._month_body.pack(fill="x")

        hdr = self._fixed_row(self._month_body, _HDR_H)
        ctk.CTkLabel(hdr, text="NAMA", font=FONT_LABEL, text_color=COLOR_TEXT_DISABLED,
                     anchor="w").pack(side="left", fill="x", expand=True)
        for cap, col in (("TOT", COLOR_TEXT_DIM), ("PAP", COLOR_SECONDARY),
                         ("DIN", _TEAL)):
            ctk.CTkLabel(hdr, text=cap, font=FONT_LABEL, text_color=col,
                         width=_NUM_W, anchor="e").pack(side="right")
        self._month_head = hdr

        # Baris ter-pool tinggal di host sendiri, jadi pemisah & baris TOTAL
        # tetap berada di bawahnya walau pool bertambah.
        self._month_host = ctk.CTkFrame(self._month_body, fg_color="transparent")
        self._month_host.pack(fill="x")
        self._month_host.grid_columnconfigure(0, weight=1)

        # tk.Frame, bukan CTkFrame: CTkFrame menggambar lewat canvas ber-sudut
        # membulat dan garis setinggi 1px hilang sama sekali pada penskalaan
        # DPI 125%. tk.Frame adalah primitif yang tepat untuk garis rambut.
        self._month_sep = tk.Frame(self._month_body, bg=COLOR_BORDER, height=1)
        self._month_sep.pack(fill="x", padx=(0, _SCROLL_PAD), pady=SPACE_XS)
        tot = self._fixed_row(self._month_body, _ROW_H)
        ctk.CTkLabel(tot, text="TOTAL", font=FONT_LABEL, text_color=COLOR_TEXT,
                     anchor="w").pack(side="left", fill="x", expand=True)
        self._tot_total = self._num_label(tot); self._tot_total.pack(side="right")
        self._tot_papar = self._num_label(tot, COLOR_SECONDARY); self._tot_papar.pack(side="right")
        self._tot_dinas = self._num_label(tot, _TEAL); self._tot_dinas.pack(side="right")
        self._month_foot = tot

        self._month_empty = ctk.CTkLabel(
            self._month_list, text="Belum ada pegawai aktif.", font=FONT_SMALL,
            text_color=COLOR_TEXT_MUTED)

    def _build_rank_chrome(self):
        self._rank_host = ctk.CTkFrame(self._rank_list, fg_color="transparent")
        self._rank_host.pack(fill="x")
        self._rank_host.grid_columnconfigure(0, weight=1)
        self._rank_empty = ctk.CTkLabel(
            self._rank_list, text="Belum ada pegawai aktif.", font=FONT_SMALL,
            text_color=COLOR_TEXT_MUTED)

    # ---------- bar komposisi (satu Canvas per baris) ----------
    def _make_bar(self, parent):
        c = tk.Canvas(parent, height=_BAR_H, bg=_BAR_TRACK,
                      highlightthickness=0, bd=0)
        c._pct = (0, 0, 0)
        c.bind("<Configure>", lambda _e, cv=c: self._draw_bar(cv))
        return c

    def _draw_bar(self, canvas):
        canvas.delete("seg")
        w = canvas.winfo_width()
        if w <= 1:
            return                      # belum di-layout; <Configure> memanggil lagi
        bar_pct, dinas_pct, paparan_pct = canvas._pct
        if not bar_pct:
            return                      # tanpa tugas: hanya rel kosong
        span = w * bar_pct / 100.0
        din_w = span * dinas_pct / 100.0
        if din_w > 0:
            canvas.create_rectangle(0, 0, din_w, _BAR_H, fill=_TEAL,
                                    width=0, tags="seg")
        pap_w = span * paparan_pct / 100.0
        if pap_w > 0:
            canvas.create_rectangle(din_w, 0, din_w + pap_w, _BAR_H,
                                    fill=COLOR_SECONDARY, width=0, tags="seg")

    def _set_bar(self, canvas, r):
        canvas._pct = (r["bar_pct"], r["dinas_pct"], r["paparan_pct"])
        self._draw_bar(canvas)

    # ---------- pool ----------
    def _new_month_row(self, idx):
        row = ctk.CTkFrame(self._month_host, fg_color="transparent", height=_ROW_H)
        row.grid(row=idx, column=0, sticky="ew", padx=(0, _SCROLL_PAD))
        row.pack_propagate(False)
        tot = self._num_label(row); tot.pack(side="right")
        pap = self._num_label(row, COLOR_SECONDARY); pap.pack(side="right")
        din = self._num_label(row, _TEAL); din.pack(side="right")
        who = ctk.CTkFrame(row, fg_color="transparent")
        who.pack(side="left", fill="x", expand=True)
        nama = ctk.CTkLabel(who, text="", font=FONT_SMALL, text_color=COLOR_TEXT,
                            anchor="w")
        nama.pack(side="left")
        dept = ctk.CTkLabel(who, text="", font=FONT_MONO_SMALL,
                            text_color=COLOR_TEXT_DISABLED, anchor="w")
        dept.pack(side="left", padx=(SPACE_SM, 0))
        return {"frame": row, "nama": nama, "dept": dept,
                "din": din, "pap": pap, "tot": tot}

    def _new_rank_row(self, idx):
        wrap = ctk.CTkFrame(self._rank_host, fg_color="transparent",
                            height=_RANK_ROW_H)
        wrap.grid(row=idx, column=0, sticky="ew", padx=(0, _SCROLL_PAD))
        wrap.pack_propagate(False)
        # Garis aksen tier di kiri (pilihan desain user — lihat spec §4.4).
        # Tinggi eksplisit, BUKAN fill="y": fill akan mengunci diri ke tinggi
        # default CTkFrame (200px) dan meregangkan seluruh baris.
        accent = ctk.CTkFrame(wrap, width=3, height=_RANK_ROW_H - 8,
                              corner_radius=2, fg_color=_ACCENT_REST)
        accent.pack(side="left", padx=(0, SPACE_SM))
        pos = ctk.CTkLabel(wrap, text="", font=FONT_MONO_SMALL, width=14,
                           anchor="e", text_color=COLOR_TEXT_MUTED)
        pos.pack(side="left")
        body = ctk.CTkFrame(wrap, fg_color="transparent")
        body.pack(side="left", fill="both", expand=True, padx=(SPACE_SM, 0))
        line = ctk.CTkFrame(body, fg_color="transparent", height=_ROW_H)
        line.pack(fill="x")
        line.pack_propagate(False)
        tot = self._num_label(line); tot.pack(side="right")
        pap = self._num_label(line, COLOR_SECONDARY); pap.pack(side="right")
        din = self._num_label(line, _TEAL); din.pack(side="right")
        nama = ctk.CTkLabel(line, text="", font=FONT_SMALL, text_color=COLOR_TEXT,
                            anchor="w")
        nama.pack(side="left", fill="x", expand=True)
        bar = self._make_bar(body)
        bar.pack(fill="x")
        return {"frame": wrap, "accent": accent, "pos": pos, "nama": nama,
                "din": din, "pap": pap, "tot": tot, "bar": bar}

    @staticmethod
    def _fit_pool(pool, factory, needed):
        """Tumbuhkan pool seperlunya, sembunyikan sisanya. grid_remove()
        mempertahankan posisi baris sehingga urutan tetap benar saat dipakai lagi."""
        while len(pool) < needed:
            pool.append(factory(len(pool)))
        for i, entry in enumerate(pool):
            if i < needed:
                entry["frame"].grid()
            else:
                entry["frame"].grid_remove()

    # ---------- render ----------
    def _render_month(self):
        rows = self._month_rows
        if not rows:
            self._month_body.pack_forget()
            self._month_empty.pack(pady=SPACE_LG)
            return
        self._month_empty.pack_forget()
        self._month_body.pack(fill="x")

        self._fit_pool(self._month_pool, self._new_month_row, len(rows))
        for r, e in zip(rows, self._month_pool):
            e["nama"].configure(text=r["nama"])
            e["dept"].configure(text=f"· {r['dept']}" if r["dept"] else "")
            self._set_num(e["din"], r["dinas"], _TEAL)
            self._set_num(e["pap"], r["paparan"], COLOR_SECONDARY)
            self._set_num(e["tot"], r["total"], COLOR_TEXT)
        self._set_num(self._tot_dinas, self._month_totals["dinas"], _TEAL, dim_zero=False)
        self._set_num(self._tot_papar, self._month_totals["paparan"], COLOR_SECONDARY, dim_zero=False)
        self._set_num(self._tot_total, self._month_totals["total"], COLOR_TEXT, dim_zero=False)

    def _render_rank(self):
        rows = self._rank_rows
        if not rows:
            self._rank_host.pack_forget()
            self._rank_empty.pack(pady=SPACE_LG)
            return
        self._rank_empty.pack_forget()
        self._rank_host.pack(fill="x")

        self._fit_pool(self._rank_pool, self._new_rank_row, len(rows))
        for r, e in zip(rows, self._rank_pool):
            ranked = r["total"] > 0          # nol tidak diberi warna tier
            e["accent"].configure(
                fg_color=_RANK_ACCENTS.get(r["rank"], _ACCENT_REST)
                if ranked else _ACCENT_REST)
            e["pos"].configure(
                text=str(r["rank"]),
                text_color=(_RANK_COLORS.get(r["rank"], COLOR_TEXT_MUTED)
                            if ranked else COLOR_TEXT_DISABLED))
            e["nama"].configure(
                text=f"{r['nama']} {r['mark']}".strip(),
                text_color=(COLOR_TEXT if ranked else COLOR_TEXT_MUTED))
            self._set_num(e["din"], r["dinas"], _TEAL)
            self._set_num(e["pap"], r["paparan"], COLOR_SECONDARY)
            self._set_num(e["tot"], r["total"], COLOR_TEXT)
            self._set_bar(e["bar"], r)

    # ---------- events ----------
    def _on_span(self, label):
        """Rentang hanya mempengaruhi papan peringkat — panel bulan sengaja
        tidak disentuh, itu separuh biaya render yang dulu terbuang."""
        self._span = _LABEL_TO_SPAN.get(label, DEFAULT_SPAN)
        self._load_rank()

    def _do_print(self):
        with get_connection(DB_PATH) as conn:
            html = render_dinas_recap_html(conn, self._month, self._span)
        fd, path = tempfile.mkstemp(suffix=".html", prefix="rekap_dinas_")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(html)
        open_html_in_browser(Path(path))
