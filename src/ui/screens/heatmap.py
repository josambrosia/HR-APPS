"""Heatmap launcher screen.

The heatmap itself renders in the browser (served by the local heatmap_server).
This in-app screen is a small launcher: open the dashboard, or open the
pre-print dialog and then the print report — both in an external browser window.
"""
from datetime import date

import customtkinter as ctk

from src.config import DB_PATH
from src.db.connection import get_connection
from src.db.settings import get_setting
from src.ui.browser_launcher import open_html_in_browser
from src.ui.components.heatmap_print_dialog import HeatmapPrintDialog
import src.web.heatmap_server as heatmap_server
from src.ui.theme import (
    COLOR_BG, COLOR_SURFACE, COLOR_BORDER,
    COLOR_TEXT, COLOR_TEXT_DIM, COLOR_ACCENT, COLOR_ACCENT_HOVER,
    FONT_DISPLAY, FONT_BODY, FONT_BODY_BOLD,
    SPACE_MD, SPACE_LG, SPACE_XL, RADIUS_MD,
)


class HeatmapScreen(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")

        ctk.CTkLabel(self, text="Heatmap Kehadiran", font=FONT_DISPLAY,
                     text_color=COLOR_TEXT).pack(anchor="w", padx=SPACE_XL,
                                                 pady=(SPACE_XL, SPACE_MD))
        ctk.CTkLabel(
            self,
            text=("Heatmap kehadiran bulanan tampil di jendela browser "
                  "(server lokal di komputer ini). Klik tombol di bawah untuk "
                  "membuka tampilan interaktif atau versi cetak."),
            font=FONT_BODY, text_color=COLOR_TEXT_DIM,
            wraplength=620, justify="left",
        ).pack(anchor="w", padx=SPACE_XL, pady=(0, SPACE_LG))

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(anchor="w", padx=SPACE_XL)
        ctk.CTkButton(
            row, text="🔳  Buka Heatmap di browser", command=self._open_dashboard,
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
            text_color=COLOR_BG, font=FONT_BODY_BOLD, corner_radius=RADIUS_MD,
            height=40,
        ).pack(side="left", padx=(0, SPACE_MD))
        ctk.CTkButton(
            row, text="🖨️  Cetak…", command=self._open_print,
            fg_color="transparent", border_width=1, border_color=COLOR_BORDER,
            text_color=COLOR_TEXT, hover_color=COLOR_SURFACE,
            font=FONT_BODY_BOLD, corner_radius=RADIUS_MD, height=40,
        ).pack(side="left")

    def _active_month(self) -> str:
        with get_connection(DB_PATH) as conn:
            m = get_setting(conn, "current_month", default="")
        return m or date.today().strftime("%Y-%m")

    def _open_dashboard(self):
        base = heatmap_server.ensure_started()
        open_html_in_browser(base + "/heatmap?month=" + self._active_month())

    def _open_print(self):
        HeatmapPrintDialog(self, on_confirm=self._do_print)

    def _do_print(self, scope, outlier):
        base = heatmap_server.ensure_started()
        open_html_in_browser(
            base + f"/heatmap/print?month={self._active_month()}"
            f"&scope={scope}&outlier={outlier}")
