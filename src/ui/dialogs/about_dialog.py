"""Branded About modal — shows version, build date, runtime, DB path.

Architecture mirrors v15.3 BatchResolveDialog: 3-row grid on the
toplevel (ROW_HEADER / ROW_CONTENT / ROW_FOOTER).
"""
import sys
from pathlib import Path

import customtkinter as ctk

from src.config import (
    APP_NAME, APP_VERSION, APP_BUILD_DATE, APP_TAGLINE,
    APP_BRAND_NAME, DB_PATH,
)
from src.ui.theme import (
    COLOR_ACCENT, COLOR_ACCENT_HOVER, COLOR_BG, COLOR_BORDER,
    COLOR_INFO, COLOR_SURFACE, COLOR_SURFACE_HIGH,
    COLOR_TEXT, COLOR_TEXT_DIM, COLOR_TEXT_MUTED,
    FONT_HEADING, FONT_BODY, FONT_BODY_BOLD, FONT_SMALL, FONT_LABEL,
    SPACE_XS, SPACE_SM, SPACE_MD, SPACE_LG, SPACE_XL,
    RADIUS_MD,
)


DIALOG_W = 420
DIALOG_H = 340


def _humanize_db_path(p: Path) -> str:
    """Return ~/-substituted path if under HOME, else absolute."""
    try:
        home = Path.home()
        ps = str(p)
        hs = str(home)
        if ps.startswith(hs):
            return "~" + ps[len(hs):]
    except Exception:
        pass
    return str(p)


class AboutDialog(ctk.CTkToplevel):
    """Modal — shows JTS branding, version, and runtime info."""

    ROW_HEADER  = 0
    ROW_CONTENT = 1
    ROW_FOOTER  = 2

    def __init__(self, parent):
        super().__init__(parent)
        self.title("About")
        self.resizable(False, False)
        self.configure(fg_color=COLOR_BG)
        self.transient(parent)

        sh = self.winfo_screenheight()
        sw = self.winfo_screenwidth()
        h = min(DIALOG_H, sh - 80)
        w = DIALOG_W
        x = (sw - w) // 2
        y = max(0, (sh - h) // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=0)

        self._build()

        self.after(50, lambda: (self.grab_set(), self.focus_set()))
        self.bind("<Escape>", lambda _e: self.destroy())
        self.bind("<Return>", lambda _e: self.destroy())
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _build(self):
        # === Row 0: Branded header (magenta band) ===
        header = ctk.CTkFrame(self, fg_color=COLOR_ACCENT, corner_radius=0)
        header.grid(row=self.ROW_HEADER, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        inner = ctk.CTkFrame(header, fg_color="transparent")
        inner.grid(row=0, column=0, sticky="ew",
                   padx=SPACE_XL, pady=(SPACE_LG, SPACE_MD))
        ctk.CTkLabel(
            inner, text=APP_BRAND_NAME.upper(),
            font=FONT_LABEL, text_color=COLOR_BG,
        ).pack(anchor="w")
        ctk.CTkLabel(
            inner, text=APP_NAME,
            font=FONT_HEADING, text_color=COLOR_BG,
        ).pack(anchor="w", pady=(SPACE_XS, 0))
        ctk.CTkLabel(
            inner, text=APP_TAGLINE,
            font=FONT_SMALL, text_color=COLOR_BG,
        ).pack(anchor="w")

        # === Row 1: Info table ===
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.grid(row=self.ROW_CONTENT, column=0, sticky="nsew",
                     padx=SPACE_XL, pady=SPACE_LG)
        content.grid_columnconfigure(1, weight=1)
        python_v = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        db_str = _humanize_db_path(DB_PATH)
        rows = [
            ("Versi",    APP_VERSION),
            ("Build",    APP_BUILD_DATE),
            ("Python",   python_v),
            ("Database", db_str),
        ]
        for i, (key, val) in enumerate(rows):
            ctk.CTkLabel(
                content, text=key, font=FONT_SMALL,
                text_color=COLOR_TEXT_MUTED, anchor="w",
            ).grid(row=i, column=0, sticky="w", pady=2, padx=(0, SPACE_MD))
            ctk.CTkLabel(
                content, text=val, font=FONT_BODY,
                text_color=COLOR_TEXT, anchor="w",
            ).grid(row=i, column=1, sticky="w", pady=2)

        # === Row 2: Footer with Tutup ===
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=self.ROW_FOOTER, column=0, sticky="ew",
                    padx=SPACE_XL, pady=(SPACE_MD, SPACE_LG))
        ctk.CTkButton(
            footer, text="Tutup", command=self.destroy,
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
            text_color=COLOR_BG, width=120, height=36,
            font=FONT_BODY_BOLD, corner_radius=RADIUS_MD,
        ).pack(side="right")
