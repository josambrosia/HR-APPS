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
    karyawan_teladan_top_n,
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

    def _reload(self):
        for w in self.body.winfo_children():
            w.destroy()

        start, end, label = self._period_range()
        with get_connection(DB_PATH) as conn:
            ranking = terlambat_ranking(conn, start, end)
            top5_late = top_n_terlambat(conn, start, end, 5)
            coaching = coaching_flag(conn, start, end)
            top5_teladan = karyawan_teladan_top_n(conn, start, end, 5)

        # KPI row — 3 cards (drop single Teladan)
        kpi_frame = ctk.CTkFrame(self.body, fg_color="transparent")
        kpi_frame.pack(fill="x", pady=(0, 12))
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

        # Three panels: top5 late | top5 teladan | coaching
        triple = ctk.CTkFrame(self.body, fg_color="transparent")
        triple.pack(fill="x", pady=(8, 0))
        for i in range(3):
            triple.grid_columnconfigure(i, weight=1)

        # Top 5 Terlambat
        late_box = ctk.CTkFrame(triple, fg_color=COLOR_PANEL, corner_radius=8)
        late_box.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        ctk.CTkLabel(late_box, text="🔥 Top 5 Terlambat",
                     font=(FONT_FAMILY, 13, "bold"), text_color=COLOR_ACCENT
                     ).pack(anchor="w", padx=12, pady=8)
        if not top5_late:
            ctk.CTkLabel(late_box, text="Tidak ada keterlambatan.",
                         text_color=COLOR_TEXT_DIM).pack(padx=12, pady=4)
        for r in top5_late:
            row = ctk.CTkFrame(late_box, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=2)
            ctk.CTkLabel(row, text=f"{r['nama']} ({r['dept']})",
                         text_color=COLOR_TEXT).pack(side="left")
            ctk.CTkLabel(row, text=f"{r['total_terlambat']} mnt",
                         text_color=COLOR_ACCENT).pack(side="right")

        # Top 5 Teladan
        teladan_box = ctk.CTkFrame(triple, fg_color=COLOR_PANEL, corner_radius=8)
        teladan_box.grid(row=0, column=1, sticky="nsew", padx=4)
        ctk.CTkLabel(teladan_box, text="🏆 Top 5 Teladan",
                     font=(FONT_FAMILY, 13, "bold"), text_color=COLOR_OK
                     ).pack(anchor="w", padx=12, pady=8)
        if not top5_teladan:
            ctk.CTkLabel(teladan_box, text="Belum ada data.",
                         text_color=COLOR_TEXT_DIM).pack(padx=12, pady=4)
        medals = ["🥇", "🥈", "🥉", "4.", "5."]
        for idx, r in enumerate(top5_teladan):
            row = ctk.CTkFrame(teladan_box, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=2)
            ctk.CTkLabel(row, text=f"{medals[idx]} {r['nama']}",
                         text_color=COLOR_TEXT).pack(side="left")
            ctk.CTkLabel(row, text=f"skor {r['score']}",
                         text_color=COLOR_OK).pack(side="right")

        # Butuh Coaching
        coach_box = ctk.CTkFrame(triple, fg_color=COLOR_PANEL, corner_radius=8)
        coach_box.grid(row=0, column=2, sticky="nsew", padx=(4, 0))
        ctk.CTkLabel(coach_box, text="⚠ Butuh Coaching",
                     font=(FONT_FAMILY, 13, "bold"), text_color=COLOR_WARN
                     ).pack(anchor="w", padx=12, pady=8)
        if not coaching:
            ctk.CTkLabel(coach_box, text="Tidak ada. ✓",
                         text_color=COLOR_TEXT_DIM).pack(padx=12, pady=4)
        for r in coaching:
            row = ctk.CTkFrame(coach_box, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=2)
            ctk.CTkLabel(row, text=f"{r['nama']} · {r['total_terlambat']} mnt",
                         text_color=COLOR_TEXT).pack(side="left")

        # Ranking lengkap (unchanged from before)
        rank_box = ctk.CTkFrame(self.body, fg_color=COLOR_PANEL, corner_radius=8)
        rank_box.pack(fill="both", expand=True, pady=(8, 0))
        ctk.CTkLabel(rank_box, text="📋 Ranking Lengkap",
                     font=(FONT_FAMILY, 13, "bold"), text_color=COLOR_TEXT
                     ).pack(anchor="w", padx=12, pady=(8, 4))
        hdr = ctk.CTkFrame(rank_box, fg_color="transparent")
        hdr.pack(fill="x", padx=12)
        for col, w in (("NAMA", 200), ("DEPT", 140), ("TERLAMBAT", 100),
                       ("HARI TELAT", 90), ("ISSUE", 70)):
            ctk.CTkLabel(hdr, text=col, font=(FONT_FAMILY, 10, "bold"),
                         text_color=COLOR_TEXT_DIM, width=w, anchor="w"
                         ).pack(side="left")
        inner = ctk.CTkScrollableFrame(rank_box, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=12, pady=4)
        for r in ranking:
            row = ctk.CTkFrame(inner, fg_color="transparent")
            row.pack(fill="x", pady=1)
            for val, w in (
                (r["nama"], 200), (r["dept"] or "-", 140),
                (f"{r['total_terlambat']} mnt", 100),
                (str(r["hari_telat"]), 90), (str(r["issue_count"]), 70),
            ):
                ctk.CTkLabel(row, text=val, font=(FONT_FAMILY, 12),
                             text_color=COLOR_TEXT, width=w, anchor="w"
                             ).pack(side="left")

    def _on_print(self):
        from src.ui.browser_launcher import open_html_in_browser
        from src.ui.components.toast import show_success_toast

        start, end, label = self._period_range()
        out_dir = Path(tempfile.gettempdir())
        try:
            with get_connection(DB_PATH) as conn:
                html_path = render_dashboard_html(
                    conn, period_start=start, period_end=end,
                    period_label=label, out_dir=out_dir,
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
                    "Gunakan Ctrl+P untuk Save as PDF."
                ),
            )
        else:
            # Browser exe not found — give user a copyable path
            messagebox.showwarning(
                "Browser tidak ditemukan",
                f"Tidak menemukan browser (Edge/Chrome/Firefox).\n\n"
                f"File HTML tersimpan di:\n{html_path}\n\n"
                "Buka manual: klik kanan → Open with → pilih browser."
            )
