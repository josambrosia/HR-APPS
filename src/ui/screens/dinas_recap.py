"""Layar Rekap Dinas Paparan — tiga panel.

Kiri   : bulan aktif (Dinas / Paparan / Total + grand total). Klik judul kolom
         untuk mengurutkan; klik lagi membalik arah.
Tengah : papan peringkat DINAS sepanjang rentang (3 bln / 6 bln / Tahun ini).
Kanan  : papan peringkat PAPARAN, rentangnya sendiri.

Pegawai yang dikecualikan lewat tombol "Kecualikan" disembunyikan dari ketiga
panel dan dari cetakan — penyaringannya terjadi di satu tempat
(reports.dinas_recap_print.build_dinas_recap_context) agar tak pernah beda.

Performa (v24): baris TIDAK dibangun ulang saat data berganti. Widget dikumpulkan
dalam pool dan diperbarui lewat configure(); baris berlebih di-grid_remove() agar
posisinya kembali utuh saat dipakai lagi. Bar digambar pada SATU tk.Canvas per
baris, bukan frame bersarang. Mengganti rentang satu papan tidak menyentuh papan
lain maupun panel bulan.

Cetak merender dinas_recap_print.html.j2 ke temp file lalu membukanya di browser
(Ctrl-P / Save PDF), mengikuti kedua rentang yang aktif di layar.
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
    SPANS, DEFAULT_SPAN, rank_by, resolve_range, sort_month_rows, span_label)
from src.core.session_state import data_version
from src.core.week_utils import MONTH_NAMES_ID, full_month_range
from src.db.attendance import count_dinas_paparan_by_employee
from src.db.connection import get_connection
from src.db.dinas_exclusions import list_excluded_ids
from src.db.settings import get_setting
from src.reports.dinas_recap_print import render_dinas_recap_html
from src.ui.browser_launcher import open_html_in_browser
from src.ui import motion
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

# Kolom panel bulan yang bisa diklik untuk mengurutkan.
_SORT_COLUMNS = (("nama", "NAMA"), ("dinas", "DIN"),
                 ("paparan", "PAP"), ("total", "TOT"))


# ---------- bar satu metrik (satu Canvas per baris) ----------
def _make_metric_bar(parent, color):
    c = tk.Canvas(parent, height=_BAR_H, bg=_BAR_TRACK, highlightthickness=0, bd=0)
    c._pct = 0
    c._color = color
    c.bind("<Configure>", lambda _e, cv=c: _draw_metric_bar(cv))
    return c


def _draw_metric_bar(canvas):
    canvas.delete("seg")
    w = canvas.winfo_width()
    if w <= 1:
        return                      # belum di-layout; <Configure> memanggil lagi
    if not canvas._pct:
        return                      # tanpa tugas: hanya rel kosong
    canvas.create_rectangle(0, 0, w * canvas._pct / 100.0, _BAR_H,
                            fill=canvas._color, width=0, tags="seg")


def _num_label(parent, color=COLOR_TEXT, width=_NUM_W):
    return ctk.CTkLabel(parent, text="", font=FONT_MONO_SMALL, width=width,
                        anchor="e", text_color=color)


def _set_num(label, value, color, *, dim_zero=True):
    label.configure(
        text=str(value),
        text_color=(COLOR_TEXT_DISABLED if (dim_zero and not value) else color))


def _fixed_row(parent, height, *, scroll_pad=True):
    f = ctk.CTkFrame(parent, fg_color="transparent", height=height)
    f.pack(fill="x", padx=(0, _SCROLL_PAD) if scroll_pad else 0)
    f.pack_propagate(False)
    return f


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


class _MetricPanel:
    """Papan peringkat satu metrik — dipakai dua kali (Dinas & Paparan).

    Menyimpan widget-nya sendiri termasuk pool baris, jadi kedua papan tidak
    saling menyentuh saat salah satunya berganti rentang.
    """

    def __init__(self, parent, *, title, color, on_span):
        self.color = color
        self._pool = []
        self._on_span_cb = on_span

        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(1, weight=1)

        head = ctk.CTkFrame(parent, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=SPACE_MD, pady=(SPACE_SM, SPACE_XS))
        ctk.CTkLabel(head, text=title, font=FONT_MONO_SMALL,
                     text_color=COLOR_TEXT_DIM).pack(side="left")
        self.span_ctl = ctk.CTkSegmentedButton(
            head, values=[label for _sid, label in SPANS], command=self._handle_span,
            fg_color=COLOR_SURFACE_HIGH, selected_color=COLOR_ACCENT,
            selected_hover_color=COLOR_ACCENT_HOVER, unselected_color=COLOR_SURFACE_HIGH,
            unselected_hover_color=COLOR_BORDER, text_color=COLOR_TEXT,
            font=FONT_SMALL, corner_radius=RADIUS_MD)
        self.span_ctl.set(dict(SPANS)[DEFAULT_SPAN])
        self.span_ctl.pack(side="right")

        # Pil geser di belakang tombol span terpilih (v25 item 13). tk.Frame,
        # bukan CTkFrame — lihat pelajaran DPI item 02 di motion.slide_pill.
        self._pill = tk.Frame(self.span_ctl, bg=COLOR_ACCENT)
        # Dipasang sejak konstruksi lewat after_idle (setelah tombol punya
        # geometri), sama seperti WeekNavBar. Kalau ditunda sampai klik
        # pertama, perpindahan rentang PERTAMA menempuh jalur "belum ter-map
        # -> place() langsung" alias tidak meluncur — padahal konsistensi
        # itulah alasan item 13 ada.
        self.span_ctl.after_idle(self._sync_pill)

        self.span_lbl = ctk.CTkLabel(parent, text="", font=FONT_MONO_SMALL,
                                     text_color=COLOR_TEXT_DISABLED, anchor="w")
        self.span_lbl.grid(row=2, column=0, sticky="ew", padx=SPACE_MD, pady=(0, SPACE_SM))

        self._list = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        self._list.grid(row=1, column=0, sticky="nsew", padx=SPACE_SM, pady=(0, SPACE_XS))
        self._list.grid_columnconfigure(0, weight=1)
        self._host = ctk.CTkFrame(self._list, fg_color="transparent")
        self._host.pack(fill="x")
        self._host.grid_columnconfigure(0, weight=1)
        self._empty = ctk.CTkLabel(self._list, text="Belum ada pegawai aktif.",
                                   font=FONT_SMALL, text_color=COLOR_TEXT_MUTED)

    # ---------- pool ----------
    def _new_row(self, idx):
        wrap = ctk.CTkFrame(self._host, fg_color="transparent", height=_RANK_ROW_H)
        wrap.grid(row=idx, column=0, sticky="ew", padx=(0, _SCROLL_PAD))
        wrap.pack_propagate(False)
        # Garis aksen tier di kiri (pilihan desain user — lihat spec §4.4).
        # Tinggi eksplisit, BUKAN fill="y": fill mengunci diri ke tinggi default
        # CTkFrame (200px) dan meregangkan seluruh baris.
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
        val = _num_label(line, self.color)
        val.pack(side="right")
        nama = ctk.CTkLabel(line, text="", font=FONT_SMALL, text_color=COLOR_TEXT,
                            anchor="w")
        nama.pack(side="left", fill="x", expand=True)
        bar = _make_metric_bar(body, self.color)
        bar.pack(fill="x")
        return {"frame": wrap, "accent": accent, "pos": pos, "nama": nama,
                "val": val, "bar": bar}

    # ---------- span (segmented button) ----------
    def _handle_span(self, label):
        self._on_span_cb(label)
        self._sync_pill()

    def _sync_pill(self):
        if not self.span_ctl.winfo_exists():
            return              # panel sudah dihancurkan sebelum idle jalan
        btn = self.span_ctl._buttons_dict.get(self.span_ctl.get())
        if btn is not None:
            motion.slide_pill(self._pill, btn)

    # ---------- render ----------
    def render(self, rows, span_text, animate=False):
        self.span_lbl.configure(text=span_text)
        if not rows:
            self._host.pack_forget()
            self._empty.pack(pady=SPACE_LG)
            return
        self._empty.pack_forget()
        self._host.pack(fill="x")
        _fit_pool(self._pool, self._new_row, len(rows))
        for r, e in zip(rows, self._pool):
            ranked = r["value"] > 0          # nol tidak diberi warna tier
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
            _set_num(e["val"], r["value"], self.color)
            # Bar tumbuh dari nol saat data benar-benar berubah (v25 item 07);
            # sekadar bolak-balik menu (cache re-display) menggambar langsung.
            if animate:
                motion.grow_bar(e["bar"], r["bar_pct"])
            else:
                e["bar"]._pct = r["bar_pct"]
                _draw_metric_bar(e["bar"])


class DinasRecapScreen(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._month = self._read_active_month()
        self._span = DEFAULT_SPAN            # rentang papan Dinas
        self._paparan_span = DEFAULT_SPAN    # rentang papan Paparan
        self._sort_key = "total"
        self._sort_desc = True
        self._month_rows = []
        self._month_totals = {"dinas": 0, "paparan": 0, "total": 0}
        self._month_pool = []
        self._sort_headers = {}
        # Sidik jari render — bar papan peringkat hanya tumbuh dari nol saat
        # data benar-benar berubah, bukan setiap kali layar cache ditampilkan
        # lagi (v25 item 07, sama seperti item 05 di heatmap).
        self._anim_sig = motion.RenderSignature()

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

    def _rows_for(self, conn, span, excluded):
        start, end = resolve_range(self._month, span)
        return [r for r in count_dinas_paparan_by_employee(conn, start, end)
                if r["employee_id"] not in excluded]

    def _load_month(self):
        start, end = full_month_range(self._month)
        with get_connection(DB_PATH) as conn:
            excluded = list_excluded_ids(conn)
            rows = count_dinas_paparan_by_employee(conn, start, end)
        self._month_rows = [r for r in rows if r["employee_id"] not in excluded]
        self._month_totals = {
            "dinas": sum(r["dinas"] for r in self._month_rows),
            "paparan": sum(r["paparan"] for r in self._month_rows),
            "total": sum(r["total"] for r in self._month_rows),
        }
        self._month_title.configure(
            text=f"◆ BULAN TERPILIH · {self._month_label().upper()}")
        n_ex = len(excluded)
        self._month_count.configure(
            text=(f"{len(self._month_rows)} pegawai" if not n_ex
                  else f"{len(self._month_rows)} pegawai · {n_ex} disembunyikan"))
        self._render_month()

    def _load_dinas(self, animate=False):
        with get_connection(DB_PATH) as conn:
            excluded = list_excluded_ids(conn)
            rows = self._rows_for(conn, self._span, excluded)
        self._dinas_panel.render(rank_by(rows, "dinas"),
                                 span_label(self._month, self._span), animate)

    def _load_paparan(self, animate=False):
        with get_connection(DB_PATH) as conn:
            excluded = list_excluded_ids(conn)
            rows = self._rows_for(conn, self._paparan_span, excluded)
        self._paparan_panel.render(rank_by(rows, "paparan"),
                                   span_label(self._month, self._paparan_span), animate)

    def _load(self):
        self._load_month()
        # Satu keputusan animasi untuk seluruh siklus load ini — dipanggil
        # SEKALI dan dipakai bagi kedua papan, supaya render pertama layar
        # menumbuhkan keduanya bersamaan alih-alih hanya papan yang lebih
        # dulu digambar.
        animate = self._anim_sig.changed(
            data_version.get(), self._month, self._span, self._paparan_span)
        self._load_dinas(animate)
        self._load_paparan(animate)

    def on_show(self) -> None:
        """Kontrak shell: dipanggil tiap layar cache ditampilkan lagi.
        Mengikuti current_month bila berubah saat layar tersembunyi; pilihan
        rentang & urutan pengguna dipertahankan."""
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
        ctk.CTkButton(
            head, text="Kecualikan…", command=self._open_exclude, width=118,
            fg_color="transparent", border_width=1, border_color=COLOR_BORDER,
            text_color=COLOR_TEXT, hover_color=COLOR_SURFACE,
            font=FONT_BODY_BOLD, corner_radius=RADIUS_MD,
        ).pack(side="right", padx=(0, SPACE_SM))

    def _panel(self, parent, col, last=False):
        box = ctk.CTkFrame(parent, fg_color=COLOR_SURFACE, border_width=1,
                           border_color=COLOR_BORDER, corner_radius=RADIUS_MD)
        box.grid(row=0, column=col, sticky="nsew",
                 padx=(0 if col == 0 else SPACE_SM, 0 if last else SPACE_SM))
        return box

    def _build_body(self):
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=SPACE_XL, pady=(0, SPACE_LG))
        body.grid_columnconfigure(0, weight=12, uniform="p")
        body.grid_columnconfigure(1, weight=9, uniform="p")
        body.grid_columnconfigure(2, weight=9, uniform="p")
        body.grid_rowconfigure(0, weight=1)

        # ---- panel 1: bulan terpilih ----
        left = self._panel(body, 0)
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(1, weight=1)
        lhead = ctk.CTkFrame(left, fg_color="transparent")
        lhead.grid(row=0, column=0, sticky="ew", padx=SPACE_MD, pady=(SPACE_SM, SPACE_XS))
        self._month_title = ctk.CTkLabel(lhead, text="", font=FONT_MONO_SMALL,
                                         text_color=COLOR_TEXT_DIM)
        self._month_title.pack(side="left")
        self._month_count = ctk.CTkLabel(lhead, text="", font=FONT_MONO_SMALL,
                                         text_color=COLOR_TEXT_DISABLED)
        self._month_count.pack(side="right")
        self._month_list = ctk.CTkScrollableFrame(left, fg_color="transparent")
        self._month_list.grid(row=1, column=0, sticky="nsew", padx=SPACE_SM,
                              pady=(0, SPACE_SM))
        self._month_list.grid_columnconfigure(0, weight=1)
        self._build_month_chrome()

        # ---- panel 2 & 3: papan peringkat per metrik ----
        mid = self._panel(body, 1)
        self._dinas_panel = _MetricPanel(
            mid, title="🏆 DINAS", color=_TEAL, on_span=self._on_dinas_span)
        right = self._panel(body, 2, last=True)
        self._paparan_panel = _MetricPanel(
            right, title="🏆 PAPARAN", color=COLOR_SECONDARY,
            on_span=self._on_paparan_span)

    def _build_month_chrome(self):
        # Seluruh isi panel hidup dalam SATU container yang di-pack sekali, jadi
        # urutan header → baris → pemisah → TOTAL terkunci saat dibangun.
        # pack() pada widget yang sudah dikelola tidak memindahkan posisinya.
        self._month_body = ctk.CTkFrame(self._month_list, fg_color="transparent")
        self._month_body.pack(fill="x")

        hdr = _fixed_row(self._month_body, _HDR_H)
        # Judul kolom bisa diklik untuk mengurutkan; klik lagi membalik arah.
        name_key, name_cap = _SORT_COLUMNS[0]
        name_lbl = ctk.CTkLabel(hdr, text=name_cap, font=FONT_LABEL, cursor="hand2",
                                text_color=COLOR_TEXT_DISABLED, anchor="w")
        name_lbl.pack(side="left", fill="x", expand=True)
        name_lbl.bind("<Button-1>", lambda _e, k=name_key: self._on_sort(k))
        self._sort_headers[name_key] = (name_lbl, name_cap)

        # pack(side="right") menumpuk dari kanan ke kiri: yang dipack lebih dulu
        # berada paling kanan. Iterasi DIBALIK agar judul sejajar dengan urutan
        # angka di baris data (_new_month_row memack tot → pap → din).
        for key, cap in reversed(_SORT_COLUMNS[1:]):
            lbl = ctk.CTkLabel(hdr, text=cap, font=FONT_LABEL, cursor="hand2",
                               text_color=COLOR_TEXT_DISABLED, anchor="e",
                               width=_NUM_W)
            lbl.pack(side="right")
            lbl.bind("<Button-1>", lambda _e, k=key: self._on_sort(k))
            self._sort_headers[key] = (lbl, cap)

        self._month_host = ctk.CTkFrame(self._month_body, fg_color="transparent")
        self._month_host.pack(fill="x")
        self._month_host.grid_columnconfigure(0, weight=1)

        # tk.Frame, bukan CTkFrame: CTkFrame menggambar lewat canvas ber-sudut
        # membulat dan garis setinggi 1px hilang sama sekali pada penskalaan
        # DPI 125%. tk.Frame adalah primitif yang tepat untuk garis rambut.
        self._month_sep = tk.Frame(self._month_body, bg=COLOR_BORDER, height=1)
        self._month_sep.pack(fill="x", padx=(0, _SCROLL_PAD), pady=SPACE_XS)

        tot = _fixed_row(self._month_body, _ROW_H)
        ctk.CTkLabel(tot, text="TOTAL", font=FONT_LABEL, text_color=COLOR_TEXT,
                     anchor="w").pack(side="left", fill="x", expand=True)
        self._tot_total = _num_label(tot); self._tot_total.pack(side="right")
        self._tot_papar = _num_label(tot, COLOR_SECONDARY); self._tot_papar.pack(side="right")
        self._tot_dinas = _num_label(tot, _TEAL); self._tot_dinas.pack(side="right")

        self._month_empty = ctk.CTkLabel(
            self._month_list, text="Belum ada pegawai aktif.", font=FONT_SMALL,
            text_color=COLOR_TEXT_MUTED)

    # ---------- pool panel bulan ----------
    def _new_month_row(self, idx):
        row = ctk.CTkFrame(self._month_host, fg_color="transparent", height=_ROW_H)
        row.grid(row=idx, column=0, sticky="ew", padx=(0, _SCROLL_PAD))
        row.pack_propagate(False)
        tot = _num_label(row); tot.pack(side="right")
        pap = _num_label(row, COLOR_SECONDARY); pap.pack(side="right")
        din = _num_label(row, _TEAL); din.pack(side="right")
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

    def _refresh_sort_headers(self):
        """Kolom aktif disorot + diberi panah arah; sisanya diredupkan."""
        arrow = "▼" if self._sort_desc else "▲"
        for key, (lbl, cap) in self._sort_headers.items():
            active = key == self._sort_key
            lbl.configure(text=f"{cap} {arrow}" if active else cap,
                          text_color=COLOR_TEXT if active else COLOR_TEXT_DISABLED)

    def _render_month(self):
        rows = sort_month_rows(self._month_rows, self._sort_key,
                               descending=self._sort_desc)
        self._refresh_sort_headers()
        if not rows:
            self._month_body.pack_forget()
            self._month_empty.pack(pady=SPACE_LG)
            return
        self._month_empty.pack_forget()
        self._month_body.pack(fill="x")

        _fit_pool(self._month_pool, self._new_month_row, len(rows))
        for r, e in zip(rows, self._month_pool):
            e["nama"].configure(text=r["nama"])
            e["dept"].configure(text=f"· {r['dept']}" if r["dept"] else "")
            _set_num(e["din"], r["dinas"], _TEAL)
            _set_num(e["pap"], r["paparan"], COLOR_SECONDARY)
            _set_num(e["tot"], r["total"], COLOR_TEXT)
        _set_num(self._tot_dinas, self._month_totals["dinas"], _TEAL, dim_zero=False)
        _set_num(self._tot_papar, self._month_totals["paparan"], COLOR_SECONDARY, dim_zero=False)
        _set_num(self._tot_total, self._month_totals["total"], COLOR_TEXT, dim_zero=False)

    # ---------- events ----------
    def _on_sort(self, key):
        """Klik kolom yang sama membalik arah; kolom baru mulai menurun
        (nama mulai menaik — A–Z yang diharapkan orang)."""
        if key == self._sort_key:
            self._sort_desc = not self._sort_desc
        else:
            self._sort_key = key
            self._sort_desc = key != "nama"
        self._render_month()

    def _on_dinas_span(self, label):
        self._span = _LABEL_TO_SPAN.get(label, DEFAULT_SPAN)
        animate = self._anim_sig.changed(
            data_version.get(), self._month, self._span, self._paparan_span)
        self._load_dinas(animate)

    def _on_paparan_span(self, label):
        self._paparan_span = _LABEL_TO_SPAN.get(label, DEFAULT_SPAN)
        animate = self._anim_sig.changed(
            data_version.get(), self._month, self._span, self._paparan_span)
        self._load_paparan(animate)

    def _open_exclude(self):
        from src.ui.components.dinas_exclude_dialog import DinasExcludeDialog
        DinasExcludeDialog(self, on_saved=self._load)

    def _do_print(self):
        with get_connection(DB_PATH) as conn:
            html = render_dinas_recap_html(conn, self._month, self._span,
                                           self._paparan_span)
        fd, path = tempfile.mkstemp(suffix=".html", prefix="rekap_dinas_")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(html)
        open_html_in_browser(Path(path))
