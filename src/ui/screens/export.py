from pathlib import Path
from tkinter import filedialog, messagebox
import customtkinter as ctk

from src.config import DB_PATH
from src.db.connection import get_connection
from src.core.report_filler import fill_monthly_report
from src.ui.components.kpi_card import KPICard
from src.ui.theme import (
    COLOR_BG, COLOR_SURFACE, COLOR_SURFACE_HIGH,
    COLOR_BORDER,
    COLOR_ACCENT, COLOR_ACCENT_HOVER,
    COLOR_INFO, COLOR_SUCCESS, COLOR_WARN,
    COLOR_TEXT, COLOR_TEXT_MUTED,
    FONT_DISPLAY,
    FONT_BODY_BOLD, FONT_LABEL,
    FONT_MONO_DATA,
    SPACE_XS, SPACE_SM, SPACE_MD, SPACE_LG,
    RADIUS_MD,
)


class ExportScreen(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self._selected: Path | None = None
        self._build()

    def _build(self):
        # Header
        ctk.CTkLabel(
            self, text="Export Laporan Bulanan",
            font=FONT_DISPLAY, text_color=COLOR_TEXT,
        ).pack(anchor="w", pady=(0, SPACE_LG))

        # ── File picker card ──
        picker = ctk.CTkFrame(
            self, fg_color=COLOR_SURFACE,
            border_width=1, border_color=COLOR_BORDER,
            corner_radius=RADIUS_MD,
        )
        picker.pack(fill="x", pady=(0, SPACE_LG))

        ctk.CTkLabel(
            picker, text="FILE LAPORAN BULANAN",
            font=FONT_LABEL, text_color=COLOR_TEXT_MUTED,
        ).pack(anchor="w", padx=SPACE_LG, pady=(SPACE_MD, SPACE_XS))

        # Path display row (mono font) + Browse button
        path_row = ctk.CTkFrame(picker, fg_color="transparent")
        path_row.pack(fill="x", padx=SPACE_LG, pady=(0, SPACE_MD))

        self.path_label = ctk.CTkLabel(
            path_row, text="(belum ada file dipilih)",
            font=FONT_MONO_DATA, text_color=COLOR_TEXT_MUTED,
            anchor="w",
        )
        self.path_label.pack(side="left", fill="x", expand=True)

        ctk.CTkButton(
            path_row, text="📁 Browse",
            command=self._pick,
            fg_color="transparent",
            border_width=1, border_color=COLOR_INFO,
            text_color=COLOR_INFO,
            hover_color=COLOR_SURFACE_HIGH,
            font=FONT_BODY_BOLD,
            width=120,
        ).pack(side="right", padx=(SPACE_SM, 0))

        # ── Matching preview cards (shown after export runs) ──
        self.preview_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.preview_frame.pack(fill="x", pady=(0, SPACE_LG))

        # ── Action row ──
        action_row = ctk.CTkFrame(self, fg_color="transparent")
        action_row.pack(fill="x")

        self.export_btn = ctk.CTkButton(
            action_row, text="💾 Export filled .xlsx",
            command=self._do_export,
            state="disabled",
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
            text_color=COLOR_BG,
            font=FONT_BODY_BOLD,
        )
        self.export_btn.pack(side="right")

    def _render_preview_cards(self, filled: int, na: int, not_found: int):
        for child in self.preview_frame.winfo_children():
            child.destroy()

        self.preview_frame.grid_columnconfigure(0, weight=1)
        self.preview_frame.grid_columnconfigure(1, weight=1)
        self.preview_frame.grid_columnconfigure(2, weight=1)

        cards = [
            ("Filled", str(filled), COLOR_SUCCESS),
            ("NA", str(na), COLOR_WARN),
            ("Not Found", str(not_found), COLOR_WARN),
        ]
        for col, (label, value, value_color) in enumerate(cards):
            KPICard(
                self.preview_frame, label, value,
                value_color=value_color, mono=True,
            ).grid(row=0, column=col, sticky="nsew", padx=SPACE_XS, pady=0)

    def _pick(self):
        path = filedialog.askopenfilename(
            title="Pilih Laporan Bulanan",
            filetypes=[("Excel", "*.xlsx")],
        )
        if not path:
            return
        self._selected = Path(path)
        self.path_label.configure(
            text=str(self._selected), text_color=COLOR_TEXT,
        )
        self.export_btn.configure(state="normal")

    def _do_export(self):
        if not self._selected:
            return
        try:
            with get_connection(DB_PATH) as conn:
                out_path, summary = fill_monthly_report(self._selected, conn)
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return

        self._render_preview_cards(
            filled=summary.filled_count,
            na=summary.na_count,
            not_found=summary.not_found_count,
        )
        messagebox.showinfo(
            "Sukses",
            f"File: {out_path.name}\n"
            f"Filled: {summary.filled_count} · "
            f"NA: {summary.na_count} · "
            f"Not found: {summary.not_found_count}",
        )
