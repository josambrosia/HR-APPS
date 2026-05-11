"""Modal dialog to customize dashboard print: pick sections + theme."""
from typing import Callable, Optional

import customtkinter as ctk

from src.ui.theme import (
    COLOR_PANEL, COLOR_ACCENT, COLOR_OK, COLOR_TEXT, COLOR_TEXT_DIM,
    FONT_FAMILY,
)


SECTION_DEFS = [
    ("kpi",          "KPI Cards (Total Terlambat, Hari Absen, Coaching Flag)"),
    ("top5_late",    "Top 5 Paling Terlambat"),
    ("top5_teladan", "Top 5 Karyawan Teladan"),
    ("coaching",     "Butuh Coaching"),
    ("departemen",   "Ranking Departemen"),
    ("hari_rawan",   "Hari Paling Rawan"),
    ("ranking",      "Ranking Keterlambatan Lengkap"),
]

THEME_DEFS = [
    ("default",     "Default (Premium Light)"),
    ("editorial",   "Editorial (Newspaper/Magazine)"),
    ("dark_glass",  "Dark Glass (Analytics Dashboard)"),
    ("infographic", "Infographic (Bold & Colorful)"),
    ("corporate",   "Corporate (Annual Report)"),
]


class PrintOptionsDialog(ctk.CTkToplevel):
    """Modal options dialog. Calls on_submit(sections_dict, theme_str)
    when user clicks Cetak; closes on Batal or window close."""

    def __init__(
        self,
        parent,
        on_submit: Callable[[dict, str], None],
        initial_sections: Optional[dict] = None,
        initial_theme: str = "default",
    ):
        super().__init__(parent)
        self.title("Pilih Opsi Cetak")
        self.geometry("520x560")
        self.resizable(False, False)
        self.configure(fg_color=COLOR_PANEL)
        self.transient(parent)

        # Center on parent
        parent.update_idletasks()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        w, h = 520, 560
        x = px + (pw - w) // 2
        y = py + (ph - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

        self._on_submit = on_submit
        self._sections_state = {k: True for k, _ in SECTION_DEFS}
        if initial_sections:
            self._sections_state.update(initial_sections)
        self._theme_state = initial_theme
        self._build()

        self.after(50, lambda: (self.grab_set(), self.focus_set()))
        self.bind("<Escape>", lambda _e: self._on_cancel())
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

    def _build(self):
        # Header
        ctk.CTkLabel(
            self, text="Opsi Cetak Dashboard",
            font=(FONT_FAMILY, 16, "bold"), text_color=COLOR_TEXT,
        ).pack(anchor="w", padx=20, pady=(16, 8))
        ctk.CTkLabel(
            self, text="Pilih bagian yang akan dicetak dan tema desainnya.",
            font=(FONT_FAMILY, 11), text_color=COLOR_TEXT_DIM,
        ).pack(anchor="w", padx=20, pady=(0, 12))

        # Sections
        ctk.CTkLabel(
            self, text="BAGIAN", font=(FONT_FAMILY, 10, "bold"),
            text_color=COLOR_ACCENT,
        ).pack(anchor="w", padx=20, pady=(4, 4))
        self._check_vars: dict[str, ctk.BooleanVar] = {}
        for key, label in SECTION_DEFS:
            var = ctk.BooleanVar(value=self._sections_state[key])
            self._check_vars[key] = var
            cb = ctk.CTkCheckBox(
                self, text=label, variable=var, font=(FONT_FAMILY, 12),
                text_color=COLOR_TEXT,
            )
            cb.pack(anchor="w", padx=28, pady=2)

        # Theme
        ctk.CTkLabel(
            self, text="TEMA", font=(FONT_FAMILY, 10, "bold"),
            text_color=COLOR_ACCENT,
        ).pack(anchor="w", padx=20, pady=(16, 4))
        self._theme_var = ctk.StringVar(value=self._theme_state)
        for key, label in THEME_DEFS:
            rb = ctk.CTkRadioButton(
                self, text=label, value=key, variable=self._theme_var,
                font=(FONT_FAMILY, 12), text_color=COLOR_TEXT,
            )
            rb.pack(anchor="w", padx=28, pady=2)

        # Buttons
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=(20, 16), side="bottom")
        ctk.CTkButton(
            btn_row, text="Batal", command=self._on_cancel,
            fg_color="transparent", hover_color=COLOR_PANEL,
            border_width=1, border_color=COLOR_TEXT_DIM,
            text_color=COLOR_TEXT, width=120,
        ).pack(side="right", padx=(8, 0))
        ctk.CTkButton(
            btn_row, text="Cetak", command=self._on_ok,
            fg_color=COLOR_OK, text_color="#1E104E", width=140,
        ).pack(side="right")

    def _on_ok(self):
        sections = {k: v.get() for k, v in self._check_vars.items()}
        theme = self._theme_var.get()
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()
        self._on_submit(sections, theme)

    def _on_cancel(self):
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()
