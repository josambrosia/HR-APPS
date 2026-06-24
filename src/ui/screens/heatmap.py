"""In-app attendance heatmap screen (customtkinter + tk.Canvas).

The dense per-employee grid is painted on a single tk.Canvas (fast for ~1k+
cells); toolbar / legend / detail strip are CTk widgets. Hover a cell for a
floating tooltip; click to pin its detail to the strip. Search + sort + month
nav repaint in place. Print renders heatmap_print.html.j2 to a temp file and
opens it in the browser (Ctrl-P / Save PDF) — no server.
See docs/superpowers/specs/2026-06-10-v18-heatmap-dashboard-design.md.
"""
import os
import tempfile
from pathlib import Path
from datetime import date

import tkinter as tk
import customtkinter as ctk

from src.config import DB_PATH
from src.db.connection import get_connection
from src.db.settings import get_setting
from src.core.heatmap import build_heatmap_context, sort_employees
from src.reports.heatmap_print import render_heatmap_print_html
from src.ui.browser_launcher import open_html_in_browser
from src.ui.components.search_bar import SearchBar
from src.ui.components.heatmap_print_dialog import HeatmapPrintDialog
from src.ui.theme import (
    COLOR_BG, COLOR_SURFACE, COLOR_SURFACE_HIGH, COLOR_BORDER, COLOR_ERROR,
    COLOR_TEXT, COLOR_TEXT_DIM, COLOR_TEXT_MUTED,
    FONT_FAMILY, FONT_DISPLAY, FONT_BODY, FONT_BODY_BOLD, FONT_SMALL,
    SPACE_XS, SPACE_SM, SPACE_MD, SPACE_LG, SPACE_XL, RADIUS_MD,
)

_PAD = 14
_CARD_GAP = 10
_CARD_PAD = 12
_NAME_W = 116
_WD_W = 22
_CELL_W = 30
_CELL_H = 22
_CELL_GAP = 3
_HEAD_H = 16
_COL_GAP = 16
_SPOT_W = 178
_SUM_W = 150

_SORT_OPTIONS = {
    "Nama (A–Z)": "nama",
    "Kehadiran terendah": "kehadiran",
    "Paling sering telat": "telat",
    "Paling sering absen": "absen",
}


class HeatmapScreen(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)

        with get_connection(DB_PATH) as conn:
            m = get_setting(conn, "current_month", default="")
        self._month = m or date.today().strftime("%Y-%m")
        self._query = ""
        self._sortkey = "nama"
        self._ctx = None
        self._cell_by_item = {}
        self._visible_employees = []
        self._tip = None
        self._ncols = None

        self._build_header()
        self._build_toolbar()
        self._legend = ctk.CTkFrame(self, fg_color="transparent")
        self._legend.grid(row=2, column=0, sticky="ew", padx=SPACE_XL, pady=(0, SPACE_XS))
        self._build_detail_strip()
        self._build_canvas()
        self._load()

        self._search.install_shortcuts(self)
        self.bind("<Destroy>", self._on_destroy_cleanup)

    # ---------- build ----------
    def _build_header(self):
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=SPACE_XL, pady=(SPACE_LG, SPACE_XS))
        ctk.CTkLabel(head, text="Heatmap Kehadiran", font=FONT_DISPLAY,
                     text_color=COLOR_TEXT).pack(side="left")
        self._subtitle = ctk.CTkLabel(head, text="", font=FONT_SMALL, text_color=COLOR_TEXT_DIM)
        self._subtitle.pack(side="left", padx=(SPACE_MD, 0))

    def _build_toolbar(self):
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=1, column=0, sticky="ew", padx=SPACE_XL, pady=(0, SPACE_SM))
        self._search = SearchBar(bar, on_change=self._on_search, width=240)
        self._search.pack(side="left")
        self._sort_var = ctk.StringVar(value="Nama (A–Z)")
        ctk.CTkOptionMenu(
            bar, values=list(_SORT_OPTIONS.keys()), variable=self._sort_var,
            command=self._on_sort, width=190,
            fg_color=COLOR_SURFACE_HIGH, button_color=COLOR_SURFACE_HIGH,
            button_hover_color=COLOR_BORDER, text_color=COLOR_TEXT, font=FONT_SMALL,
        ).pack(side="left", padx=(SPACE_SM, 0))
        ctk.CTkButton(bar, text="🖨️  Cetak…", command=self._open_print,
                      fg_color="transparent", border_width=1, border_color=COLOR_BORDER,
                      text_color=COLOR_TEXT, hover_color=COLOR_SURFACE,
                      font=FONT_BODY_BOLD, corner_radius=RADIUS_MD, width=110
                      ).pack(side="right")
        self._next_btn = ctk.CTkButton(bar, text="›", width=34, command=self._go_next,
                                       fg_color=COLOR_SURFACE_HIGH, hover_color=COLOR_BORDER,
                                       text_color=COLOR_TEXT, font=FONT_BODY_BOLD)
        self._next_btn.pack(side="right", padx=(SPACE_XS, SPACE_MD))
        self._month_lbl = ctk.CTkLabel(bar, text="", font=FONT_BODY_BOLD,
                                       text_color=COLOR_TEXT, width=120)
        self._month_lbl.pack(side="right")
        self._prev_btn = ctk.CTkButton(bar, text="‹", width=34, command=self._go_prev,
                                       fg_color=COLOR_SURFACE_HIGH, hover_color=COLOR_BORDER,
                                       text_color=COLOR_TEXT, font=FONT_BODY_BOLD)
        self._prev_btn.pack(side="right", padx=(0, SPACE_XS))

    def _render_legend(self):
        for w in self._legend.winfo_children():
            w.destroy()
        for item in (self._ctx["legend"] if self._ctx else []):
            chip = ctk.CTkFrame(self._legend, fg_color="transparent")
            chip.pack(side="left", padx=(0, SPACE_MD))
            ctk.CTkLabel(chip, text=item["code"], width=22, height=16,
                         fg_color=item["color"], text_color=item["text_color"],
                         font=(FONT_FAMILY, 10, "bold"), corner_radius=4).pack(side="left", padx=(0, 4))
            ctk.CTkLabel(chip, text=item["label"], font=FONT_SMALL,
                         text_color=COLOR_TEXT_DIM).pack(side="left")

    def _build_detail_strip(self):
        strip = ctk.CTkFrame(self, fg_color=COLOR_SURFACE_HIGH, border_width=1,
                             border_color=COLOR_BORDER, corner_radius=RADIUS_MD)
        strip.grid(row=3, column=0, sticky="ew", padx=SPACE_XL, pady=(SPACE_XS, SPACE_SM))
        self._detail_var = ctk.StringVar(value="Klik sel untuk detail.")
        ctk.CTkLabel(strip, textvariable=self._detail_var, font=FONT_SMALL,
                     text_color=COLOR_TEXT, anchor="w").pack(side="left", padx=SPACE_MD, pady=6)

    def _build_canvas(self):
        wrap = ctk.CTkFrame(self, fg_color="transparent")
        wrap.grid(row=4, column=0, sticky="nsew", padx=SPACE_XL, pady=(0, SPACE_LG))
        wrap.grid_columnconfigure(0, weight=1)
        wrap.grid_rowconfigure(0, weight=1)
        self._canvas = tk.Canvas(wrap, bg=COLOR_BG, highlightthickness=0, bd=0)
        self._canvas.grid(row=0, column=0, sticky="nsew")
        sb = ctk.CTkScrollbar(wrap, command=self._canvas.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self._canvas.configure(yscrollcommand=sb.set)
        self._canvas.bind("<MouseWheel>",
                          lambda e: self._canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))
        self._canvas.tag_bind("cell", "<Motion>", self._on_cell_motion)
        self._canvas.tag_bind("cell", "<Leave>", lambda e: self._hide_tip())
        self._canvas.tag_bind("cell", "<Button-1>", self._on_cell_click)
        self._canvas.bind("<Configure>", self._on_canvas_configure)

    # ---------- data / nav ----------
    def _load(self):
        with get_connection(DB_PATH) as conn:
            self._ctx = build_heatmap_context(conn, self._month, exclude_outliers=False,
                                              today=date.today())
        self._month_lbl.configure(text=self._ctx["month_label"])
        self._subtitle.configure(
            text=("Hover sel untuk tooltip, klik untuk detail. "
                  f"Hari kerja efektif {self._ctx['month_label']}: "
                  f"{self._ctx['eff_hari_kerja']} hari."))
        self._render_legend()
        self._repaint()

    def _go_prev(self):
        self._month = self._ctx["prev_month"]
        self._load()

    def _go_next(self):
        self._month = self._ctx["next_month"]
        self._load()

    def _on_search(self, q):
        self._query = q
        self._repaint()

    def _on_sort(self, label):
        self._sortkey = _SORT_OPTIONS.get(label, "nama")
        self._repaint()

    # ---------- paint ----------
    def _visible(self):
        emps = self._ctx["employees"]
        q = self._query.lower().strip()
        if q:
            emps = [e for e in emps if q in (e["nama"] + " " + e.get("dept", "")).lower()]
        return sort_employees(emps, self._sortkey)

    def _card_width(self, nweeks):
        grid_w = _WD_W + nweeks * (_CELL_W + _CELL_GAP)
        return (_CARD_PAD + _NAME_W + _COL_GAP + grid_w + _COL_GAP + 8
                + _SPOT_W + _COL_GAP + _SUM_W + _CARD_PAD)

    def _on_canvas_configure(self, event):
        # Re-flow into more/fewer columns only when the column count actually
        # changes (avoids a repaint on every pixel of a window drag).
        if not self._ctx or self._ctx.get("is_empty"):
            return
        card_w = self._card_width(len(self._ctx["weeks"]))
        ncols = max(1, int((event.width - _PAD) // (card_w + _CARD_GAP)))
        if ncols != self._ncols:
            self._repaint()

    def _repaint(self):
        c = self._canvas
        c.delete("all")
        self._cell_by_item = {}
        total = len(self._ctx["employees"]) if self._ctx else 0
        if not self._ctx or self._ctx["is_empty"]:
            c.create_text(20, 36, anchor="nw", fill=COLOR_TEXT_DIM, font=FONT_BODY,
                          text="Belum ada data untuk bulan ini — import data fingerprint dulu.")
            self._visible_employees = []
            self._search.set_count(0, total)
            c.configure(scrollregion=(0, 0, 0, 80))
            return
        emps = self._visible()
        self._visible_employees = emps
        self._search.set_count(len(emps), total)
        if not emps:
            c.create_text(20, 36, anchor="nw", fill=COLOR_TEXT_DIM, font=FONT_BODY,
                          text="Tidak ada hasil.")
            c.configure(scrollregion=(0, 0, 0, 80))
            return
        ctx = self._ctx
        card_w = self._card_width(len(ctx["weeks"]))
        card_h = _HEAD_H + 7 * (_CELL_H + _CELL_GAP) + 2 * _CARD_PAD
        avail = max(c.winfo_width(), card_w + 2 * _PAD)
        ncols = max(1, int((avail - _PAD) // (card_w + _CARD_GAP)))
        self._ncols = ncols
        for i, e in enumerate(emps):
            col, r = i % ncols, i // ncols
            self._paint_card(e, _PAD + col * (card_w + _CARD_GAP),
                             _PAD + r * (card_h + _CARD_GAP))
        nrows = (len(emps) + ncols - 1) // ncols
        c.configure(scrollregion=(0, 0, 0, _PAD + nrows * (card_h + _CARD_GAP)))

    def _round_rect(self, x0, y0, x1, y1, r, **kw):
        pts = [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1,
               x1 - r, y1, x0 + r, y1, x0, y1, x0, y1 - r, x0, y0 + r, x0, y0]
        return self._canvas.create_polygon(pts, smooth=True, **kw)

    def _paint_card(self, e, x, y):
        c = self._canvas
        ctx = self._ctx
        weeks = ctx["weeks"]
        nweeks = len(weeks)
        grid_w = _WD_W + nweeks * (_CELL_W + _CELL_GAP)
        gx = x + _CARD_PAD + _NAME_W + _COL_GAP
        sx = gx + grid_w + _COL_GAP + 8
        rx = sx + _SPOT_W + _COL_GAP
        card_right = rx + _SUM_W + _CARD_PAD
        grid_h = _HEAD_H + 7 * (_CELL_H + _CELL_GAP)
        card_h = grid_h + 2 * _CARD_PAD
        self._round_rect(x, y, card_right, y + card_h, RADIUS_MD,
                         fill=COLOR_SURFACE, outline=COLOR_BORDER)
        if e.get("needs_attention"):
            c.create_rectangle(x, y + 6, x + 3, y + card_h - 6, fill=COLOR_ERROR, outline="")
        nx, ny = x + _CARD_PAD, y + _CARD_PAD
        c.create_text(nx, ny, anchor="nw", fill=COLOR_TEXT, font=FONT_BODY_BOLD, text=e["nama"])
        if e.get("dept"):
            c.create_text(nx, ny + 18, anchor="nw", fill=COLOR_TEXT_MUTED, font=FONT_SMALL, text=e["dept"])
        if e.get("needs_attention"):
            c.create_text(nx, ny + 40, anchor="nw", fill=COLOR_ERROR,
                          font=(FONT_FAMILY, 10, "bold"), text="● Perlu perhatian")
        gy = y + _CARD_PAD
        for w in range(nweeks):
            cx = gx + _WD_W + w * (_CELL_W + _CELL_GAP)
            c.create_text(cx + _CELL_W / 2, gy, anchor="n", fill=COLOR_TEXT_MUTED,
                          font=(FONT_FAMILY, 10, "bold"), text=f"M{w + 1}")
        wd_labels = ctx["weekday_labels"]
        today_day = ctx.get("today_day")
        for wd in range(7):
            ry = gy + _HEAD_H + wd * (_CELL_H + _CELL_GAP)
            c.create_text(gx + _WD_W - 4, ry + _CELL_H / 2, anchor="e", fill=COLOR_TEXT_DIM,
                          font=(FONT_FAMILY, 10, "bold"), text=wd_labels[wd])
            for w in range(nweeks):
                day = weeks[w][wd]
                if day == 0:
                    continue
                cell = e["cells"][day]
                cx = gx + _WD_W + w * (_CELL_W + _CELL_GAP)
                rid = c.create_rectangle(cx, ry, cx + _CELL_W, ry + _CELL_H,
                                         fill=cell["color"], outline="", tags=("cell", "cellrect"))
                tid = c.create_text(cx + 4, ry + 2, anchor="nw", fill=cell["text_color"],
                                    font=(FONT_FAMILY, 10, "bold"), text=str(day), tags=("cell",))
                self._cell_by_item[rid] = cell
                self._cell_by_item[tid] = cell
                if today_day and day == today_day:
                    c.create_rectangle(cx, ry, cx + _CELL_W, ry + _CELL_H,
                                       outline=COLOR_TEXT, width=2)
        self._paint_sorotan(sx, y + _CARD_PAD, e["sorotan"])
        self._paint_summary(rx, y + _CARD_PAD, e)
        return y + card_h

    def _paint_sorotan(self, sx, sy, s):
        c = self._canvas
        c.create_line(sx - 10, sy, sx - 10, sy + 166, fill=COLOR_BORDER)
        c.create_text(sx, sy, anchor="nw", fill=COLOR_TEXT_DIM, font=FONT_SMALL, text="Kehadiran")
        c.create_text(sx + _SPOT_W - 12, sy - 4, anchor="ne", fill=s["pct_color"],
                      font=(FONT_FAMILY, 18, "bold"), text=f"{s['pct_hadir']}%")
        by = sy + 26
        c.create_rectangle(sx, by, sx + _SPOT_W - 12, by + 6, fill=COLOR_BORDER, outline="")
        fillw = int((_SPOT_W - 12) * min(max(s["pct_hadir"], 0), 100) / 100)
        if fillw > 0:
            c.create_rectangle(sx, by, sx + fillw, by + 6, fill=s["pct_color"], outline="")
        c.create_text(sx, by + 11, anchor="nw", fill=COLOR_TEXT, font=(FONT_FAMILY, 12, "bold"),
                      text=f"{s['hk']}/{s['work_days']}")
        c.create_text(sx + 48, by + 13, anchor="nw", fill=COLOR_TEXT_MUTED,
                      font=(FONT_FAMILY, 10), text="hari kerja dihadiri")
        ly = by + 34
        for i, line in enumerate((
                f"Tepat waktu {s['ontime_days']} hari",
                f"Telat {s['telat_total']} mnt · {s['telat_days']} hari",
                f"Dinas {s['dinas']} · Sakit {s['sakit']}")):
            c.create_text(sx, ly + i * 18, anchor="nw", fill=COLOR_TEXT_DIM, font=FONT_SMALL, text=line)

    def _paint_summary(self, rx, sy, e):
        c = self._canvas
        c.create_line(rx - 10, sy, rx - 10, sy + 166, fill=COLOR_BORDER)
        c.create_text(rx, sy, anchor="nw", fill=COLOR_TEXT_MUTED, font=FONT_SMALL,
                      text=f"Ringkasan — HK {e['hk']}")
        summ = e["summary"]
        for i, m in enumerate(self._ctx["summary_meta"]):
            col, row = i % 2, i // 2
            ex = rx + col * 74
            ey = sy + 22 + row * 18
            c.create_rectangle(ex, ey + 2, ex + 10, ey + 12, fill=m["color"], outline="")
            c.create_text(ex + 16, ey, anchor="nw", fill=COLOR_TEXT_DIM, font=FONT_SMALL,
                          text=f"{m['code']} {summ[m['code']]}")

    # ---------- hover / click ----------
    def _current_cell(self):
        item = self._canvas.find_withtag("current")
        return self._cell_by_item.get(item[0]) if item else None

    def _on_cell_motion(self, event):
        cell = self._current_cell()
        if cell:
            self._show_tip(event, cell)

    def _show_tip(self, event, cell):
        if self._tip is None:
            self._tip = tk.Toplevel(self)
            self._tip.wm_overrideredirect(True)
            self._tip_lbl = tk.Label(self._tip, justify="left", bg="#000000", fg="#FFFFFF",
                                     font=(FONT_FAMILY, 9), bd=1, relief="solid", padx=8, pady=6)
            self._tip_lbl.pack()
        self._tip_lbl.configure(text=(
            f"{cell['label']}\n"
            f"Tanggal {cell['date']} · Masuk {cell['masuk']} · Keluar {cell['keluar']}\n"
            f"Telat {cell['telat']} · Alasan {cell['alasan']}"))
        self._tip.wm_geometry(f"+{event.x_root + 14}+{event.y_root + 12}")
        self._tip.deiconify()

    def _hide_tip(self):
        if self._tip is not None:
            self._tip.withdraw()

    def _on_cell_click(self, _event):
        cell = self._current_cell()
        if cell:
            self._show_detail(cell)

    def _show_detail(self, cell):
        self._detail_var.set(
            f"{cell['date']} {self._ctx['month_label']} · {cell['label']} · "
            f"Masuk {cell['masuk']} · Keluar {cell['keluar']} · "
            f"Telat {cell['telat']} · Alasan {cell['alasan']}")

    # ---------- print ----------
    def _open_print(self):
        HeatmapPrintDialog(self, on_confirm=self._do_print)

    def _do_print(self, scope, outlier):
        with get_connection(DB_PATH) as conn:
            html = render_heatmap_print_html(conn, self._month, scope=scope, outlier=outlier)
        fd, path = tempfile.mkstemp(suffix=".html", prefix="heatmap_")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(html)
        open_html_in_browser(Path(path))

    # ---------- cleanup ----------
    def _on_destroy_cleanup(self, _e=None):
        if self._tip is not None:
            try:
                self._tip.destroy()
            except Exception:
                pass
