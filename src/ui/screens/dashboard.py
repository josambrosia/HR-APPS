import tempfile
from datetime import date, timedelta
from pathlib import Path

import customtkinter as ctk
from tkinter import messagebox

from src.config import DB_PATH
from src.db.connection import get_connection
from src.db.settings import get_setting
from src.core.insights import (
    terlambat_ranking, top_n_terlambat, coaching_flag,
    karyawan_teladan_top_n, ranking_departemen, hari_paling_rawan,
)
from src.core.week_utils import weeks_in_month, full_month_range
from src.reports.html_renderer import render_dashboard_html
from src.ui.components.kpi_card import KPICard
from src.ui.components.week_nav import WeekNavBar
from src.ui.theme import (
    FONT_FAMILY, COLOR_OK, COLOR_WARN, COLOR_ACCENT, COLOR_PANEL,
    COLOR_TEXT, COLOR_TEXT_DIM,
)


class DashboardScreen(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        with get_connection(DB_PATH) as conn:
            self._current_month = get_setting(conn, "current_month") or ""

        self._build_header()
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.grid(row=1, column=0, sticky="nsew")
        self._reload()

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 16))

        ctk.CTkLabel(
            header, text="Dashboard", font=(FONT_FAMILY, 24, "bold"),
            text_color=COLOR_TEXT,
        ).pack(side="left", padx=(0, 16))

        self.nav = WeekNavBar(
            header, current_month=self._current_month,
            on_change=self._on_period_change, initial="semua",
        )
        self.nav.pack(side="left")

        ctk.CTkButton(
            header, text="📄 Cetak / Export PDF",
            fg_color=COLOR_OK, text_color="#1E104E",
            command=self._on_print,
        ).pack(side="right", padx=(8, 0))

    def _on_period_change(self, _key):
        self._reload()

    def _period_range(self):
        if not self._current_month:
            today = date.today()
            return (today - timedelta(days=30)).isoformat(), today.isoformat(), "Last 30 days"
        if self.nav.active == "semua":
            start, end = full_month_range(self._current_month)
            return start, end, f"Bulanan ({self._current_month})"
        try:
            num = int(self.nav.active.split("_")[1])
        except (IndexError, ValueError):
            num = 1
        for n, start, end in weeks_in_month(self._current_month):
            if n == num:
                return start, end, f"Minggu {n} ({start} → {end})"
        start, end = full_month_range(self._current_month)
        return start, end, f"Bulanan ({self._current_month})"

    def _dynamic_coaching_threshold(self, start_iso: str, end_iso: str) -> int:
        """Threshold scales with period length: 75 min per calendar week."""
        s = date.fromisoformat(start_iso)
        e = date.fromisoformat(end_iso)
        days = (e - s).days + 1  # inclusive
        weeks = max(1, (days + 6) // 7)  # ceil
        return 75 * weeks

    def _reload(self):
        for w in self.body.winfo_children():
            w.destroy()

        # Two-column body: left dense panels (60%) + right tall Ranking (40%)
        self.body.grid_columnconfigure(0, weight=3)
        self.body.grid_columnconfigure(1, weight=2)
        self.body.grid_rowconfigure(1, weight=1)

        start, end, label = self._period_range()
        dynamic_threshold = self._dynamic_coaching_threshold(start, end)

        with get_connection(DB_PATH) as conn:
            ranking = terlambat_ranking(conn, start, end)
            top5_late = top_n_terlambat(conn, start, end, 5)
            coaching = coaching_flag(conn, start, end, threshold=dynamic_threshold)
            top5_teladan = karyawan_teladan_top_n(conn, start, end, 5)
            dept_rows = ranking_departemen(conn, start, end)
            day_rows = hari_paling_rawan(conn, start, end)

        # ─────── KPI ROW ───────
        kpi_frame = ctk.CTkFrame(self.body, fg_color="transparent")
        kpi_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        for i in range(3):
            kpi_frame.grid_columnconfigure(i, weight=1)

        total_late = sum(r["total_terlambat"] for r in ranking)
        KPICard(kpi_frame, "Periode", label).grid(row=0, column=0, padx=4, sticky="ew")
        KPICard(kpi_frame, "Total Terlambat", f"{total_late} mnt",
                value_color=COLOR_ACCENT
                ).grid(row=0, column=1, padx=4, sticky="ew")
        KPICard(kpi_frame, "Coaching Flag", str(len(coaching)),
                value_color=COLOR_WARN
                ).grid(row=0, column=2, padx=4, sticky="ew")

        # ─────── LEFT: dense 2×3 panel grid ───────
        left = ctk.CTkFrame(self.body, fg_color="transparent")
        left.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
        left.grid_columnconfigure(0, weight=1)
        left.grid_columnconfigure(1, weight=1)

        PANEL_H_REGULAR = 220
        PANEL_H_HARI = 150

        def make_panel(parent, title, color, fixed_height: int,
                       scrollable: bool = True):
            """Fixed-height panel with header. Content area scrolls if scrollable=True
            (use for variable-length lists like Coaching), or is a plain frame
            otherwise (use for bounded lists like Top 5)."""
            box = ctk.CTkFrame(parent, fg_color=COLOR_PANEL, corner_radius=8,
                               height=fixed_height)
            box.grid_propagate(False)
            box.grid_columnconfigure(0, weight=1)
            box.grid_rowconfigure(1, weight=1)

            ctk.CTkLabel(
                box, text=title,
                font=(FONT_FAMILY, 12, "bold"), text_color=color,
            ).grid(row=0, column=0, sticky="w", padx=10, pady=(8, 4))

            if scrollable:
                content = ctk.CTkScrollableFrame(
                    box, fg_color="transparent", corner_radius=0,
                )
            else:
                content = ctk.CTkFrame(box, fg_color="transparent")
            content.grid(row=1, column=0, sticky="nsew", padx=4, pady=(0, 6))
            return box, content

        def populate_two_col(scroll_frame, rows, empty_msg, left_fn, right_fn,
                             right_color):
            if not rows:
                ctk.CTkLabel(scroll_frame, text=empty_msg,
                             text_color=COLOR_TEXT_DIM,
                             font=(FONT_FAMILY, 11)).pack(padx=8, pady=4)
                return
            for r in rows:
                row = ctk.CTkFrame(scroll_frame, fg_color="transparent")
                row.pack(fill="x", padx=6, pady=1)
                ctk.CTkLabel(row, text=left_fn(r), font=(FONT_FAMILY, 11),
                             text_color=COLOR_TEXT, anchor="w").pack(side="left")
                ctk.CTkLabel(row, text=right_fn(r), font=(FONT_FAMILY, 11),
                             text_color=right_color, anchor="e"
                             ).pack(side="right")

        # Row 0: Top 5 Terlambat | Top 5 Teladan (bounded — non-scrollable)
        late_box, late_content = make_panel(
            left, "🔥 Top 5 Terlambat", COLOR_ACCENT, PANEL_H_REGULAR,
            scrollable=False)
        late_box.grid(row=0, column=0, sticky="nsew", padx=(0, 4), pady=(0, 4))
        populate_two_col(
            late_content, top5_late, "Tidak ada keterlambatan.",
            left_fn=lambda r: r["nama"],
            right_fn=lambda r: f"{r['total_terlambat']} mnt",
            right_color=COLOR_ACCENT,
        )

        teladan_box, teladan_content = make_panel(
            left, "🏆 Top 5 Teladan", COLOR_OK, PANEL_H_REGULAR,
            scrollable=False)
        teladan_box.grid(row=0, column=1, sticky="nsew", padx=(4, 0), pady=(0, 4))
        if not top5_teladan:
            ctk.CTkLabel(teladan_content, text="Belum ada data.",
                         text_color=COLOR_TEXT_DIM,
                         font=(FONT_FAMILY, 11)).pack(padx=8, pady=4)
        else:
            medals = ["🥇", "🥈", "🥉", "4.", "5."]
            for idx, r in enumerate(top5_teladan):
                row = ctk.CTkFrame(teladan_content, fg_color="transparent")
                row.pack(fill="x", padx=6, pady=1)
                ctk.CTkLabel(row, text=f"{medals[idx]} {r['nama']}",
                             font=(FONT_FAMILY, 11), text_color=COLOR_TEXT,
                             anchor="w").pack(side="left")
                ctk.CTkLabel(row, text=f"skor {r['score']}",
                             font=(FONT_FAMILY, 11), text_color=COLOR_OK,
                             anchor="e").pack(side="right")

        # Row 1: Butuh Coaching (with dynamic threshold) | Ranking Departemen
        coach_box, coach_scroll = make_panel(
            left, f"⚠ Butuh Coaching (>{dynamic_threshold} mnt)",
            COLOR_WARN, PANEL_H_REGULAR)
        coach_box.grid(row=1, column=0, sticky="nsew", padx=(0, 4), pady=4)
        populate_two_col(
            coach_scroll, coaching, "Tidak ada. ✓",
            left_fn=lambda r: r["nama"],
            right_fn=lambda r: f"{r['total_terlambat']} mnt",
            right_color=COLOR_WARN,
        )

        dept_box, dept_scroll = make_panel(
            left, "🏢 Ranking Departemen", COLOR_ACCENT, PANEL_H_REGULAR)
        dept_box.grid(row=1, column=1, sticky="nsew", padx=(4, 0), pady=4)
        populate_two_col(
            dept_scroll, dept_rows, "Belum ada data.",
            left_fn=lambda r: f"{r['dept']} ({r['pegawai_count']})",
            right_fn=lambda r: f"{r['total_terlambat']} mnt",
            right_color=COLOR_ACCENT,
        )

        # Row 2: Hari Paling Rawan (spans both columns, shorter)
        day_box, day_scroll = make_panel(
            left, "📅 Hari Paling Rawan", COLOR_WARN, PANEL_H_HARI)
        day_box.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=(4, 0))
        populate_two_col(
            day_scroll, day_rows, "Belum ada data harian.",
            left_fn=lambda r: r["hari"],
            right_fn=lambda r: f"{r['terlambat_count']} hari telat",
            right_color=COLOR_WARN,
        )

        # ─────── RIGHT: Ranking Lengkap (tall) ───────
        rank_box = ctk.CTkFrame(self.body, fg_color=COLOR_PANEL, corner_radius=8)
        rank_box.grid(row=1, column=1, sticky="nsew")
        ctk.CTkLabel(rank_box, text="📋 Ranking Lengkap",
                     font=(FONT_FAMILY, 13, "bold"), text_color=COLOR_TEXT
                     ).pack(anchor="w", padx=12, pady=(8, 4))

        hdr = ctk.CTkFrame(rank_box, fg_color="transparent")
        hdr.pack(fill="x", padx=12)
        for col, w in (("NAMA", 130), ("DEPT", 100), ("TERLAMBAT", 80),
                       ("TELAT", 50), ("ISSUE", 50)):
            ctk.CTkLabel(hdr, text=col, font=(FONT_FAMILY, 10, "bold"),
                         text_color=COLOR_TEXT_DIM, width=w, anchor="w"
                         ).pack(side="left")

        inner = ctk.CTkScrollableFrame(rank_box, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=12, pady=4)
        for r in ranking:
            row = ctk.CTkFrame(inner, fg_color="transparent")
            row.pack(fill="x", pady=1)
            for val, w in (
                (r["nama"], 130), (r["dept"] or "-", 100),
                (f"{r['total_terlambat']} mnt", 80),
                (str(r["hari_telat"]), 50),
                (str(r["issue_count"]), 50),
            ):
                ctk.CTkLabel(row, text=val, font=(FONT_FAMILY, 11),
                             text_color=COLOR_TEXT, width=w, anchor="w"
                             ).pack(side="left")

    def _on_print(self):
        from src.ui.components.print_dialog import PrintOptionsDialog
        PrintOptionsDialog(
            self.winfo_toplevel(),
            on_submit=self._do_print,
        )

    def _do_print(self, sections: dict, theme: str):
        from src.ui.browser_launcher import open_html_in_browser
        from src.ui.components.toast import show_success_toast

        start, end, label = self._period_range()
        dynamic_threshold = self._dynamic_coaching_threshold(start, end)
        out_dir = Path(tempfile.gettempdir())
        try:
            with get_connection(DB_PATH) as conn:
                html_path = render_dashboard_html(
                    conn, period_start=start, period_end=end,
                    period_label=label, out_dir=out_dir,
                    template_name=theme, sections=sections,
                    threshold=dynamic_threshold,
                )
        except Exception as e:
            messagebox.showerror("Error generating PDF", str(e))
            return

        success, browser_name = open_html_in_browser(html_path)
        if success:
            show_success_toast(
                self.winfo_toplevel(),
                title="Dashboard Dibuka",
                message=(
                    f"Dashboard {label} dibuka di {browser_name}.\n"
                    f"Tema: {theme} · Gunakan Ctrl+P untuk Save as PDF."
                ),
            )
        else:
            messagebox.showwarning(
                "Browser tidak ditemukan",
                f"Tidak menemukan browser (Chrome/Edge/Firefox).\n\n"
                f"File HTML tersimpan di:\n{html_path}\n\n"
                "Buka manual: klik kanan → Open with → pilih browser."
            )
