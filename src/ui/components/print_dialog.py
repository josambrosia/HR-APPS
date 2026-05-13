"""Modal dialog to customize dashboard print: pick which sections to include.

Theme picker removed — there's only one theme now ("Light"). Dialog size and
position fixed for laptop screens: 560×440 centered on screen with max-height
clamp.
"""
from typing import Callable, Optional

import customtkinter as ctk

from src.ui.theme import (
    FONT_FAMILY,
    COLOR_BG, COLOR_SURFACE, COLOR_SURFACE_HIGH,
    COLOR_BORDER,
    COLOR_ACCENT, COLOR_ACCENT_HOVER,
    COLOR_INFO,
    COLOR_TEXT, COLOR_TEXT_DIM, COLOR_TEXT_MUTED,
    FONT_HEADING, FONT_BODY, FONT_BODY_BOLD, FONT_LABEL,
    SPACE_XS, SPACE_SM, SPACE_MD, SPACE_LG, SPACE_XL,
    RADIUS_LG, RADIUS_MD,
)


SECTION_DEFS = [
    ("kpi",            "KPI Cards (4 metrik utama)"),
    ("top5_late",      "Top 5 Paling Terlambat"),
    ("top5_teladan",   "Karyawan Teladan"),
    ("coaching",       "Butuh Coaching"),
    ("pola_jam_masuk", "Pola Jam Masuk"),
    ("ranking",        "Ranking Lengkap Karyawan (wajib)"),
]


DIALOG_W = 560
DIALOG_H = 440
_SCREEN_BUFFER = 100  # taskbar + title bar buffer


class PrintOptionsDialog(ctk.CTkToplevel):
    """Modal options dialog. Calls on_submit(sections_dict) when user clicks Cetak.

    Closes on Batal, Escape, or window close. The "ranking" section is always
    True regardless of checkbox state (rendered as checked + disabled).
    """

    def __init__(
        self,
        parent,
        on_submit: Callable[[dict], None],
        initial_sections: Optional[dict] = None,
    ):
        super().__init__(parent)
        self.title("Pilih Opsi Cetak")
        self.resizable(False, False)
        self.configure(fg_color=COLOR_BG)
        self.transient(parent)

        # Size with screen-height clamp, center on SCREEN (not parent)
        sh = self.winfo_screenheight()
        sw = self.winfo_screenwidth()
        h = min(DIALOG_H, sh - _SCREEN_BUFFER)
        w = DIALOG_W
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

        self._on_submit = on_submit
        self._sections_state = {k: True for k, _ in SECTION_DEFS}
        if initial_sections:
            self._sections_state.update(initial_sections)
        self._sections_state["ranking"] = True  # enforce mandatory

        self._build()

        self.after(50, lambda: (self.grab_set(), self.focus_set()))
        self.bind("<Escape>", lambda _e: self._on_cancel())
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

    def _build(self):
        # Header
        ctk.CTkLabel(
            self, text="Opsi Cetak Dashboard",
            font=FONT_HEADING, text_color=COLOR_TEXT,
        ).pack(anchor="w", padx=SPACE_XL, pady=(SPACE_LG, SPACE_XS))
        ctk.CTkLabel(
            self, text="Pilih bagian yang akan dicetak.",
            font=FONT_BODY, text_color=COLOR_TEXT_DIM,
        ).pack(anchor="w", padx=SPACE_XL, pady=(0, SPACE_MD))

        # Sections
        ctk.CTkLabel(
            self, text="BAGIAN", font=FONT_LABEL,
            text_color=COLOR_TEXT_MUTED,
        ).pack(anchor="w", padx=SPACE_XL, pady=(SPACE_XS, SPACE_XS))
        self._check_vars: dict[str, ctk.BooleanVar] = {}
        for key, label in SECTION_DEFS:
            var = ctk.BooleanVar(value=self._sections_state[key])
            self._check_vars[key] = var
            is_mandatory = (key == "ranking")
            cb = ctk.CTkCheckBox(
                self, text=label, variable=var,
                font=FONT_BODY,
                text_color=COLOR_TEXT,
                fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
                border_color=COLOR_BORDER,
                checkbox_width=18, checkbox_height=18,
                state="disabled" if is_mandatory else "normal",
            )
            cb.pack(anchor="w", padx=SPACE_XL + SPACE_SM, pady=2)

        # Buttons (sticky at bottom via side="bottom")
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=SPACE_XL, pady=(SPACE_LG, SPACE_LG), side="bottom")
        ctk.CTkButton(
            btn_row, text="Batal", command=self._on_cancel,
            fg_color="transparent",
            hover_color=COLOR_SURFACE_HIGH,
            border_width=1, border_color=COLOR_INFO,
            text_color=COLOR_INFO,
            width=160, height=40,
            font=FONT_BODY_BOLD,
            corner_radius=RADIUS_MD,
        ).pack(side="right", padx=(SPACE_MD, 0))
        ctk.CTkButton(
            btn_row, text="📄 Cetak", command=self._on_ok,
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
            text_color=COLOR_BG,
            width=180, height=40,
            font=FONT_BODY_BOLD,
            corner_radius=RADIUS_MD,
        ).pack(side="right")

    def _on_ok(self):
        sections = {k: v.get() for k, v in self._check_vars.items()}
        sections["ranking"] = True  # belt-and-suspenders for disabled checkbox
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()
        self._on_submit(sections)

    def _on_cancel(self):
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()
