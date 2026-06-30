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
from src.reports.employee_report import render_employee_report_html
from src.ui.browser_launcher import open_html_in_browser
from src.ui.components.search_bar import SearchBar
from src.ui.components.heatmap_print_dialog import HeatmapPrintDialog
from src.ui.theme import (
    COLOR_BG, COLOR_SURFACE, COLOR_SURFACE_HIGH, COLOR_BORDER, COLOR_ERROR,
    COLOR_ACCENT, COLOR_TEXT, COLOR_TEXT_DIM, COLOR_TEXT_MUTED,
    FONT_FAMILY, FONT_DISPLAY, FONT_BODY, FONT_BODY_BOLD, FONT_SMALL,
    SPACE_XS, SPACE_SM, SPACE_MD, SPACE_LG, SPACE_XL, RADIUS_MD,
)

_PAD = 14
_CARD_GAP = 10
_CARD_PAD = 12
_NAME_W = 116
_WD_W = 22
_CELL_W = 40
_CELL_H = 24
_CELL_GAP = 3
_HEAD_H = 16
_SPOT_W = 178
_SUM_W = 150

# Bento panel tones — in-app heatmap only (tk.Canvas: solid fills, no gradient/blur).
_BENTO_CARD = "#0F0F11"      # card surface, darker so the tiles read as raised
_BENTO_CARD_BD = "#242428"   # card border
_BENTO_TILE = "#17181B"      # zone-tile fill
_BENTO_TILE_BD = "#25262B"   # zone-tile border
_TILE_PAD = 10               # padding inside a tile
_TILE_GAP = 11               # gap between tiles
_RIDGE_FILL = "#201E18"      # flat area fill under the lateness ridge
# Severity ramp for the lateness ridge: on-time green → mild amber → orange → severe red.
_SEV_GREEN = "#10B981"
_SEV_AMBER = "#FBBF24"
_SEV_ORANGE = "#FB923C"
_SEV_RED = "#EF4444"


def _sev_color(minutes, tolerance, severe):
    """Colour a lateness value by how severe it is (drives the ridge contour)."""
    if minutes <= tolerance:
        return _SEV_GREEN
    if minutes < severe * 0.5:
        return _SEV_AMBER
    if minutes < severe:
        return _SEV_ORANGE
    return _SEV_RED


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
        self._cetak_hover = None
        self._ncols = None
        self._last_w = None

        self._build_header()
        self._build_toolbar()
        self._legend = ctk.CTkFrame(self, fg_color="transparent")
        self._legend.grid(row=2, column=0, sticky="ew", padx=SPACE_XL, pady=(0, SPACE_XS))
        self._build_detail_strip()
        self._build_canvas()
        self._load()

        self._search.install_shortcuts(self)
        self.bind("<Destroy>", self._on_destroy_cleanup, add="+")

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
            sw_kwargs = dict(width=22, height=16, font=(FONT_FAMILY, 10, "bold"),
                             corner_radius=4)
            if item["code"] == "–":   # nodata: hollow swatch (CTkFrame border)
                swatch = ctk.CTkFrame(chip, width=22, height=16, corner_radius=4,
                                      fg_color=COLOR_SURFACE, border_width=1,
                                      border_color=item["color"])
                swatch.pack(side="left", padx=(0, 4))
                swatch.pack_propagate(False)
                ctk.CTkLabel(swatch, text=item["code"], text_color=COLOR_TEXT_MUTED,
                             font=(FONT_FAMILY, 10, "bold"), fg_color="transparent"
                             ).pack(expand=True, fill="both")
            else:
                ctk.CTkLabel(chip, text=item["code"], fg_color=item["color"],
                             text_color=item["text_color"], **sw_kwargs
                             ).pack(side="left", padx=(0, 4))
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
        self._canvas.tag_bind("cetak", "<Button-1>", self._on_cetak_click)
        self._canvas.tag_bind("cetak", "<Enter>", self._on_cetak_enter)
        self._canvas.tag_bind("cetak", "<Leave>", self._on_cetak_leave)
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

    def _on_canvas_configure(self, event):
        if not self._ctx or self._ctx.get("is_empty"):
            return
        w = event.width
        if self._last_w is None or abs(w - self._last_w) > 8:
            self._last_w = w
            self._repaint()

    def _repaint(self):
        c = self._canvas
        c.delete("all")
        self._cell_by_item = {}
        self._cetak_hover = None
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
        avail = max(self._canvas.winfo_width(), 320)
        card_w = avail - 2 * _PAD - 20     # one card fills the row (right margin clears the scrollbar)
        card_h = _HEAD_H + 7 * (_CELL_H + _CELL_GAP) + 2 * _TILE_PAD + 2 * _CARD_PAD
        ncols = 1
        self._ncols = ncols
        for i, e in enumerate(emps):
            self._paint_card(e, _PAD, _PAD + i * (card_h + _CARD_GAP), card_w)
        c.configure(scrollregion=(0, 0, 0, _PAD + len(emps) * (card_h + _CARD_GAP)))

    def _round_rect(self, x0, y0, x1, y1, r, **kw):
        pts = [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1,
               x1 - r, y1, x0 + r, y1, x0, y1, x0, y1 - r, x0, y0 + r, x0, y0]
        return self._canvas.create_polygon(pts, smooth=True, **kw)

    def _paint_card(self, e, x, y, card_w):
        ctx = self._ctx
        nweeks = len(ctx["weeks"])
        grid_w = _WD_W + nweeks * (_CELL_W + _CELL_GAP)
        card_right = x + card_w
        tile_h = _HEAD_H + 7 * (_CELL_H + _CELL_GAP) + 2 * _TILE_PAD
        card_h = tile_h + 2 * _CARD_PAD
        ty0 = y + _CARD_PAD
        ty1 = ty0 + tile_h
        # card surface — tiles sit on top of it for a sense of depth
        self._round_rect(x, y, card_right, y + card_h, RADIUS_MD,
                         fill=_BENTO_CARD, outline=_BENTO_CARD_BD)
        # name block (not tiled)
        nx, ny = x + _CARD_PAD + 4, ty0 + 2
        self._canvas.create_text(nx, ny, anchor="nw", fill=COLOR_TEXT,
                                 font=FONT_BODY_BOLD, text=e["nama"])
        if e.get("dept"):
            self._canvas.create_text(nx, ny + 18, anchor="nw", fill=COLOR_TEXT_MUTED,
                                     font=FONT_SMALL, text=e["dept"])
        if e.get("needs_attention"):
            self._canvas.create_text(nx, ny + 40, anchor="nw", fill=COLOR_ERROR,
                                     font=(FONT_FAMILY, 10, "bold"), text="● Perlu perhatian")
        # grid tile
        gx0 = x + _CARD_PAD + _NAME_W + _TILE_GAP
        gx1 = gx0 + grid_w + 2 * _TILE_PAD
        self._round_rect(gx0, ty0, gx1, ty1, 9, fill=_BENTO_TILE, outline=_BENTO_TILE_BD)
        self._paint_grid(gx0 + _TILE_PAD, ty0 + _TILE_PAD, e)
        # Kehadiran tile
        kx0 = gx1 + _TILE_GAP
        kx1 = kx0 + _SPOT_W + 2 * _TILE_PAD
        self._round_rect(kx0, ty0, kx1, ty1, 9, fill=_BENTO_TILE, outline=_BENTO_TILE_BD)
        self._paint_sorotan(kx0 + _TILE_PAD, ty0 + _TILE_PAD, e["sorotan"])
        # Ringkasan tile
        rx0 = kx1 + _TILE_GAP
        rx1 = rx0 + _SUM_W + 2 * _TILE_PAD
        self._round_rect(rx0, ty0, rx1, ty1, 9, fill=_BENTO_TILE, outline=_BENTO_TILE_BD)
        self._paint_summary(rx0 + _TILE_PAD, ty0 + _TILE_PAD, e)
        # Pola Keterlambatan tile fills the rest; the Cetak button lives in its header
        px0 = rx1 + _TILE_GAP
        px1 = card_right - _CARD_PAD
        if px1 - px0 >= 220:
            self._round_rect(px0, ty0, px1, ty1, 9, fill=_BENTO_TILE, outline=_BENTO_TILE_BD)
            self._paint_lateness(px0 + _TILE_PAD, ty0 + _TILE_PAD,
                                 px1 - px0 - 2 * _TILE_PAD, tile_h - 2 * _TILE_PAD, e)
        return y + card_h

    def _paint_grid(self, gx, gy, e):
        c = self._canvas
        ctx = self._ctx
        weeks = ctx["weeks"]; nweeks = len(weeks)
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
                if cell["status"] == "nodata":
                    rid = c.create_rectangle(cx, ry, cx + _CELL_W, ry + _CELL_H,
                                             fill=_BENTO_TILE, outline=cell["color"],
                                             tags=("cell", "cellrect"))
                    tid = c.create_text(cx + 4, ry + 2, anchor="nw", fill=COLOR_TEXT_MUTED,
                                        font=(FONT_FAMILY, 10, "bold"), text=str(day), tags=("cell",))
                else:
                    rid = c.create_rectangle(cx, ry, cx + _CELL_W, ry + _CELL_H,
                                             fill=cell["color"], outline="", tags=("cell", "cellrect"))
                    tid = c.create_text(cx + 4, ry + 2, anchor="nw", fill=cell["text_color"],
                                        font=(FONT_FAMILY, 10, "bold"), text=str(day), tags=("cell",))
                self._cell_by_item[rid] = cell
                self._cell_by_item[tid] = cell
                if today_day and day == today_day:
                    c.create_rectangle(cx, ry, cx + _CELL_W, ry + _CELL_H,
                                       outline=COLOR_TEXT, width=2)

    def _paint_sorotan(self, sx, sy, s):
        c = self._canvas
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

    def _paint_lateness(self, tx, ty, tw, th, e):
        """The 'Pola Keterlambatan' tile: a severity-gradient ridge of daily
        lateness (a peak = a late day, height ∝ minutes, colour = how severe),
        the month's worst day spotlighted with average & half-month trend below,
        and the Cetak button in its header. Late peaks reuse the cell tooltip on
        hover. tk.Canvas can't gradient-fill, so the area is a flat tint under a
        severity-coloured contour line."""
        c = self._canvas
        ctx = self._ctx
        cells = e["cells"]
        days = ctx["days"]
        n_days = len(days)
        tol = ctx.get("late_tolerance") or 0
        sev = ctx.get("severe_threshold") or 0
        scale_max = max(sev * 1.33, 80.0)

        # header: caption (left) + Cetak button (right, always magenta)
        c.create_text(tx, ty, anchor="nw", fill=COLOR_TEXT_DIM, font=FONT_SMALL,
                      text="Pola Keterlambatan")
        bx1 = tx + tw
        bx0 = bx1 - 74
        by0, by1 = ty - 2, ty + 18
        bid = self._round_rect(bx0, by0, bx1, by1, 6, fill=COLOR_ACCENT, outline=COLOR_ACCENT)
        tid = c.create_text((bx0 + bx1) / 2, (by0 + by1) / 2, fill=COLOR_BG,
                            font=(FONT_FAMILY, 10, "bold"), text="🖨 Cetak")
        btn = {"_cetak_emp": e["employee_id"], "_bbox": (bx0, by0, bx1, by1)}
        for it in (bid, tid):
            c.addtag_withtag("cetak", it)
            self._cell_by_item[it] = btn

        # chart geometry (between the header and the bottom stat strip)
        fill_h = 64
        div_y = ty + th - fill_h
        chart_top = ty + 24
        base_y = div_y - 20
        top_y = chart_top + 8
        usable = max(base_y - top_y, 12)
        left, right = tx, tx + tw
        span = max(right - left, 1)

        def day_x(d):
            return left + (d - 0.5) / n_days * span

        def y_of(m):
            return base_y - min(m / scale_max, 1.0) * usable

        def late_min(d):
            cell = cells[d]
            if cell["status"] in ("sedang", "parah") and isinstance(cell["telat"], int):
                return cell["telat"]
            return 0

        # tolerance guide + baseline
        if tol > 0:
            ytol = y_of(tol)
            c.create_line(left, ytol, right, ytol, fill="#5A4A2A", dash=(3, 3))
            c.create_text(left + 1, ytol - 2, anchor="sw", fill=COLOR_TEXT_MUTED,
                          font=(FONT_FAMILY, 8), text=f"toleransi {tol}m")
        c.create_line(left, base_y, right, base_y, fill=COLOR_BORDER)

        # flat filled area (no gradients on tk.Canvas)
        pts = [left, base_y]
        for d in days:
            pts += [day_x(d), y_of(late_min(d))]
        pts += [right, base_y]
        c.create_polygon(pts, fill=_RIDGE_FILL, outline="")
        # severity-coloured contour, segment by segment
        prev = None
        for d in days:
            cur = (day_x(d), y_of(late_min(d)), late_min(d))
            if prev is not None:
                c.create_line(prev[0], prev[1], cur[0], cur[1],
                              fill=_sev_color(max(prev[2], cur[2]), tol, sev), width=2)
            prev = cur
        # dinas baseline ticks + late peaks (dot + minute label; hoverable via "cell")
        for d in days:
            cell = cells[d]
            st = cell["status"]
            cx = day_x(d)
            if st == "dinas":
                c.create_oval(cx - 2.4, base_y - 2.4, cx + 2.4, base_y + 2.4,
                              fill=cell["color"], outline="")
            elif st in ("sedang", "parah") and isinstance(cell["telat"], int):
                m = cell["telat"]
                py = y_of(m)
                col = _sev_color(m, tol, sev)
                did = c.create_oval(cx - 2.8, py - 2.8, cx + 2.8, py + 2.8,
                                    fill=col, outline="", tags=("cell",))
                lid = c.create_text(cx, max(py - 6, top_y - 6), anchor="s", fill=col,
                                    font=(FONT_FAMILY, 8, "bold"), text=str(m), tags=("cell",))
                self._cell_by_item[did] = cell
                self._cell_by_item[lid] = cell
        # day-of-month axis
        for d in sorted({1, 8, 15, 22, n_days}):
            if 1 <= d <= n_days:
                c.create_text(day_x(d), base_y + 3, anchor="n", fill=COLOR_TEXT_MUTED,
                              font=(FONT_FAMILY, 8), text=str(d))

        # ---- stat strip: spotlight (worst day) + average + half-month trend, as
        #      three evenly-spaced columns so wide tiles don't strand the values ----
        c.create_line(left, div_y, right, div_y, fill="#23242A")
        lt = e["lateness"]
        sy = div_y + 7
        spot_w = int(tw * 0.40)
        col1 = tx + spot_w
        col2 = col1 + (tw - spot_w) // 2
        c.create_line(col1 - 12, div_y + 6, col1 - 12, ty + th - 2, fill="#262730")
        c.create_line(col2 - 12, div_y + 6, col2 - 12, ty + th - 2, fill="#262730")
        # spotlight — Puncak Keterlambatan (worst day)
        c.create_text(tx, sy, anchor="nw", fill=COLOR_TEXT_MUTED,
                      font=(FONT_FAMILY, 8, "bold"), text="PUNCAK KETERLAMBATAN")
        if lt["worst_min"] > 0:
            wc = _sev_color(lt["worst_min"], tol, sev)
            big = c.create_text(tx, sy + 12, anchor="nw", fill=wc,
                                font=(FONT_FAMILY, 22, "bold"), text=str(lt["worst_min"]))
            bb = c.bbox(big)
            if bb:
                c.create_text(bb[2] + 1, bb[3] - 4, anchor="sw", fill=COLOR_TEXT_MUTED,
                              font=(FONT_FAMILY, 11), text="m")
            mon3 = ctx["month_label"].split()[0][:3]
            c.create_text(tx, sy + 41, anchor="nw", fill=COLOR_TEXT_DIM,
                          font=(FONT_FAMILY, 9), text=f"{lt['worst_day']} {mon3}")
        else:
            c.create_text(tx, sy + 16, anchor="nw", fill=COLOR_TEXT_DIM,
                          font=(FONT_FAMILY, 14, "bold"), text="—")
            c.create_text(tx, sy + 41, anchor="nw", fill=COLOR_TEXT_MUTED,
                          font=(FONT_FAMILY, 9), text="tidak ada")
        # average per late day
        c.create_text(col1, sy, anchor="nw", fill=COLOR_TEXT_MUTED,
                      font=(FONT_FAMILY, 8, "bold"), text="RATA² / HARI TELAT")
        c.create_text(col1, sy + 13, anchor="nw", fill=COLOR_TEXT,
                      font=(FONT_FAMILY, 16, "bold"), text=f"{lt['avg_min']}m")
        # half-month trend
        ttxt, tcol = {"up": ("↑ naik", _SEV_ORANGE),
                      "down": ("↓ turun", _SEV_GREEN),
                      "flat": ("→ tetap", COLOR_TEXT_DIM)}[lt["trend"]]
        c.create_text(col2, sy, anchor="nw", fill=COLOR_TEXT_MUTED,
                      font=(FONT_FAMILY, 8, "bold"), text="TREN ½ BULAN")
        c.create_text(col2, sy + 13, anchor="nw", fill=tcol,
                      font=(FONT_FAMILY, 15, "bold"), text=ttxt)

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

    def _on_cetak_click(self, _event):
        item = self._canvas.find_withtag("current")
        info = self._cell_by_item.get(item[0]) if item else None
        if info and "_cetak_emp" in info:
            self._print_employee(info["_cetak_emp"])
        return "break"

    def _on_cetak_enter(self, _event):
        """The button stays magenta; hover only swaps the cursor to a hand to
        signal it's clickable (like the dashboard's Cetak button)."""
        item = self._canvas.find_withtag("current")
        info = self._cell_by_item.get(item[0]) if item else None
        if not info or "_bbox" not in info:
            return
        self._cetak_hover = info
        self._canvas.configure(cursor="hand2")

    def _on_cetak_leave(self, event):
        info = self._cetak_hover
        if not info:
            return
        # The rect and its label are two items; moving between them fires Leave.
        # Only drop the hand cursor once the pointer truly exits the button box.
        cx, cy = self._canvas.canvasx(event.x), self._canvas.canvasy(event.y)
        x0, y0, x1, y1 = info["_bbox"]
        if x0 <= cx <= x1 and y0 <= cy <= y1:
            return
        self._canvas.configure(cursor="")
        self._cetak_hover = None

    def _print_employee(self, employee_id):
        with get_connection(DB_PATH) as conn:
            html = render_employee_report_html(conn, self._month, employee_id)
        fd, path = tempfile.mkstemp(suffix=".html", prefix="emp_report_")
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
