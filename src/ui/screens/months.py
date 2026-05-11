"""Riwayat Bulan screen — list all months in DB with stats and per-month actions."""
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from src.config import DB_PATH
from src.core.report_generator import (
    generate_monthly_report, month_label,
)
from src.db.attendance import list_months_with_stats
from src.db.connection import get_connection
from src.db.settings import get_setting, set_setting
from src.ui.components.toast import show_success_toast
from src.ui.theme import (
    FONT_FAMILY, COLOR_PANEL, COLOR_PANEL_OPEN, COLOR_ACCENT,
    COLOR_OK, COLOR_TEXT, COLOR_TEXT_DIM,
)


class MonthsScreen(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        with get_connection(DB_PATH) as conn:
            self._current_month = get_setting(conn, "current_month") or ""

        self._build_header()
        self._build_list()

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        ctk.CTkLabel(
            header, text="Riwayat Bulan",
            font=(FONT_FAMILY, 24, "bold"),
            text_color=COLOR_TEXT,
        ).pack(side="left")

    def _build_list(self):
        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.grid(row=1, column=0, sticky="nsew")
        self._render_cards()

    def _render_cards(self):
        for child in self.scroll.winfo_children():
            child.destroy()

        with get_connection(DB_PATH) as conn:
            months = [dict(r) for r in list_months_with_stats(conn)]

        if not months:
            self._render_empty_state()
            return

        for m in months:
            self._render_card(m)

    def _render_empty_state(self):
        empty = ctk.CTkFrame(self.scroll, fg_color=COLOR_PANEL, corner_radius=8)
        empty.pack(fill="x", pady=8, padx=4)
        ctk.CTkLabel(
            empty, text="Belum ada data.",
            font=(FONT_FAMILY, 14, "bold"), text_color=COLOR_TEXT,
        ).pack(anchor="w", padx=16, pady=(16, 4))
        ctk.CTkLabel(
            empty, text="Import fingerprint dulu via menu Import.",
            font=(FONT_FAMILY, 11), text_color=COLOR_TEXT_DIM,
        ).pack(anchor="w", padx=16, pady=(0, 16))

    def _render_card(self, m: dict):
        is_active = m["year_month"] == self._current_month
        bg = COLOR_PANEL_OPEN if is_active else COLOR_PANEL

        card = ctk.CTkFrame(self.scroll, fg_color=bg, corner_radius=8)
        card.pack(fill="x", pady=6, padx=4)

        title_row = ctk.CTkFrame(card, fg_color="transparent")
        title_row.pack(fill="x", padx=16, pady=(12, 4))
        bullet = "●" if is_active else "○"
        bullet_color = COLOR_ACCENT if is_active else COLOR_TEXT_DIM
        ctk.CTkLabel(
            title_row, text=bullet,
            font=(FONT_FAMILY, 16), text_color=bullet_color,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(
            title_row, text=month_label(m["year_month"]),
            font=(FONT_FAMILY, 16, "bold"), text_color=COLOR_TEXT,
        ).pack(side="left")
        if is_active:
            ctk.CTkLabel(
                title_row, text="(aktif)",
                font=(FONT_FAMILY, 11), text_color=COLOR_TEXT_DIM,
            ).pack(side="left", padx=(8, 0))

        stats = (f"{m['hari_count']} hari · "
                 f"{m['records_count']} records · "
                 f"{m['open_issues_count']} issue open")
        ctk.CTkLabel(
            card, text=stats,
            font=(FONT_FAMILY, 12), text_color=COLOR_TEXT_DIM,
        ).pack(anchor="w", padx=16, pady=(0, 8))

        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(fill="x", padx=12, pady=(0, 12))
        ctk.CTkButton(
            btn_row, text="Buka", width=100,
            fg_color=COLOR_OK, text_color="#1E104E",
            command=lambda ym=m["year_month"]: self._on_buka(ym),
        ).pack(side="left", padx=4)
        ctk.CTkButton(
            btn_row, text="📄 Generate Laporan", width=180,
            fg_color=COLOR_OK, text_color="#1E104E",
            command=lambda ym=m["year_month"]: self._on_generate(ym),
        ).pack(side="left", padx=4)

    def _on_buka(self, year_month: str):
        with get_connection(DB_PATH) as conn:
            set_setting(conn, "current_month", year_month)
        self._current_month = year_month
        # Navigate to Dashboard. HRApp._show is the private nav method;
        # acceptable to call from a child screen as a back-pointer.
        top = self.winfo_toplevel()
        if hasattr(top, "_show"):
            top._show("Dashboard")

    def _on_generate(self, year_month: str):
        default_name = f"Laporan Bulanan {month_label(year_month)} [Auto Filled].xlsx"
        out_path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            initialfile=default_name,
            filetypes=[("Excel files", "*.xlsx")],
            title=f"Simpan Laporan {month_label(year_month)}",
        )
        if not out_path:
            return  # cancelled

        try:
            with get_connection(DB_PATH) as conn:
                summary = generate_monthly_report(
                    conn, year_month=year_month, out_path=Path(out_path),
                )
        except Exception as e:
            messagebox.showerror(
                "Error generate laporan",
                f"Tidak bisa generate file:\n{e}",
            )
            return

        show_success_toast(
            self.winfo_toplevel(),
            title="Laporan Berhasil Dibuat",
            message=(
                f"Laporan Bulanan {month_label(year_month)} disimpan.\n"
                f"File: {out_path}\n"
                f"{summary.rows_generated} baris di-generate · "
                f"{summary.na_count} baris NA / Belum ada kabar"
            ),
        )
