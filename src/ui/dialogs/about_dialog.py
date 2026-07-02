"""Branded About modal — shows version, build date, runtime, DB path,
and a scrollable changelog of what changed per version.

Architecture: 4-row grid (ROW_HEADER / ROW_CONTENT / ROW_CHANGELOG /
ROW_FOOTER). Changelog row absorbs extra space (weight=1) so it
scrolls inside its fixed-height container while the dialog stays a
predictable size.
"""
import sys
from pathlib import Path

import customtkinter as ctk

from src.config import (
    APP_NAME, APP_VERSION, APP_BUILD_DATE, APP_TAGLINE,
    APP_BRAND_NAME, APP_CHANGELOG, DB_PATH,
)
from src.ui.theme import (
    COLOR_ACCENT, COLOR_ACCENT_HOVER, COLOR_BG, COLOR_BORDER,
    COLOR_INFO, COLOR_SUCCESS, COLOR_SURFACE, COLOR_SURFACE_HIGH,
    COLOR_TEXT, COLOR_TEXT_DIM, COLOR_TEXT_MUTED,
    COLOR_WARN,
    FONT_HEADING, FONT_BODY, FONT_BODY_BOLD, FONT_SMALL, FONT_LABEL,
    SPACE_XS, SPACE_SM, SPACE_MD, SPACE_LG, SPACE_XL,
    RADIUS_MD,
)


DIALOG_W = 540
DIALOG_H = 560


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
    """Modal — shows JTS branding, version, runtime info, and changelog."""

    ROW_HEADER    = 0
    ROW_CONTENT   = 1
    ROW_CHANGELOG = 2
    ROW_FOOTER    = 3

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
        self.grid_rowconfigure(self.ROW_HEADER,    weight=0)
        self.grid_rowconfigure(self.ROW_CONTENT,   weight=0)
        self.grid_rowconfigure(self.ROW_CHANGELOG, weight=1)
        self.grid_rowconfigure(self.ROW_FOOTER,    weight=0)

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
        content.grid(row=self.ROW_CONTENT, column=0, sticky="ew",
                     padx=SPACE_XL, pady=(SPACE_MD, SPACE_SM))
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

        # === Row 2: Scrollable changelog ===
        self._build_changelog()

        # === Row 3: Footer with Tutup ===
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=self.ROW_FOOTER, column=0, sticky="ew",
                    padx=SPACE_XL, pady=(SPACE_MD, SPACE_LG))
        ctk.CTkButton(
            footer, text="Tutup", command=self.destroy,
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
            text_color=COLOR_BG, width=120, height=36,
            font=FONT_BODY_BOLD, corner_radius=RADIUS_MD,
        ).pack(side="right")

    def _build_changelog(self):
        """Scrollable changelog showing what's new in each version."""
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.grid(row=self.ROW_CHANGELOG, column=0, sticky="nsew",
                       padx=SPACE_XL, pady=(0, SPACE_MD))
        container.grid_rowconfigure(1, weight=1)
        container.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            container, text="Apa yang baru?",
            font=FONT_BODY_BOLD, text_color=COLOR_TEXT,
            anchor="w",
        ).grid(row=0, column=0, sticky="w", pady=(0, SPACE_XS))

        scroll = ctk.CTkScrollableFrame(
            container, fg_color=COLOR_SURFACE,
            border_width=1, border_color=COLOR_BORDER,
            corner_radius=RADIUS_MD,
        )
        scroll.grid(row=1, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)

        # Color + label per kind. Semantic mapping:
        #   feat   → emerald (success)   — new functionality
        #   fix    → amber (COLOR_WARN)  — bug fix; amber is the caution
        #                                  signal, matching the token.
        #   change → cyan (info)         — behavior change
        #   remove → muted gray          — feature removal (no dedicated tag color)
        # Badge text uses COLOR_BG (dark) — works for all four backgrounds.
        kind_meta = {
            "feat":   ("BARU",  COLOR_SUCCESS),
            "fix":    ("FIX",   COLOR_WARN),
            "change": ("UBAH",  COLOR_INFO),
            "remove": ("HAPUS", COLOR_TEXT_MUTED),
        }

        for i, entry in enumerate(APP_CHANGELOG):
            # Version row
            head = ctk.CTkFrame(scroll, fg_color="transparent")
            head.grid(row=i * 2, column=0, sticky="ew",
                      pady=(SPACE_SM if i == 0 else SPACE_MD, SPACE_XS),
                      padx=SPACE_MD)
            head.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(
                head, text=f"v{entry['version']}",
                font=FONT_BODY_BOLD, text_color=COLOR_ACCENT,
            ).grid(row=0, column=0, sticky="w")
            ctk.CTkLabel(
                head, text=entry["date"],
                font=FONT_SMALL, text_color=COLOR_TEXT_DIM,
            ).grid(row=0, column=1, sticky="e")

            # Changes list
            body = ctk.CTkFrame(scroll, fg_color="transparent")
            body.grid(row=i * 2 + 1, column=0, sticky="ew",
                      padx=SPACE_MD, pady=(0, SPACE_XS))
            body.grid_columnconfigure(1, weight=1)
            for j, (kind, desc) in enumerate(entry["changes"]):
                label_text, badge_color = kind_meta.get(
                    kind, ("INFO", COLOR_TEXT_MUTED))
                # Small colored tag
                tag = ctk.CTkLabel(
                    body, text=label_text,
                    font=FONT_SMALL, text_color=COLOR_BG,
                    fg_color=badge_color,
                    corner_radius=3,
                    width=40, height=18,
                )
                tag.grid(row=j, column=0, sticky="nw", pady=2, padx=(0, SPACE_SM))
                # Description (wrapped)
                ctk.CTkLabel(
                    body, text=desc,
                    font=FONT_SMALL, text_color=COLOR_TEXT,
                    wraplength=420, justify="left", anchor="w",
                ).grid(row=j, column=1, sticky="w", pady=2)
