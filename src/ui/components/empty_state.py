"""Empty-state card — bordered surface with title + hint line.

Extracted verbatim from the `_render_empty(title, hint)` duplicated in
the Outlier and Hari Libur screens ("Belum ada bulan aktif." / "Import
fingerprint dulu via menu Import." etc.). The caller packs the card
itself (both screens use fill="x", pady=SPACE_SM, padx=SPACE_XS).
"""
import customtkinter as ctk

from src.ui.theme import (
    COLOR_SURFACE, COLOR_BORDER,
    COLOR_TEXT, COLOR_TEXT_DIM,
    FONT_SUBHEAD, FONT_SMALL,
    SPACE_XS, SPACE_LG,
    RADIUS_MD,
)


class EmptyStateCard(ctk.CTkFrame):
    """Card shown when a screen has nothing to render yet.

    Args:
        parent: parent widget
        title: main line, e.g. "Belum ada bulan aktif."
        hint: action hint below, e.g. "Pilih bulan di menu Active Month dulu."
    """

    def __init__(self, parent, title: str, hint: str):
        super().__init__(
            parent, fg_color=COLOR_SURFACE,
            border_width=1, border_color=COLOR_BORDER,
            corner_radius=RADIUS_MD,
        )
        ctk.CTkLabel(
            self, text=title, font=FONT_SUBHEAD, text_color=COLOR_TEXT,
        ).pack(anchor="w", padx=SPACE_LG, pady=(SPACE_LG, SPACE_XS))
        ctk.CTkLabel(
            self, text=hint, font=FONT_SMALL, text_color=COLOR_TEXT_DIM,
        ).pack(anchor="w", padx=SPACE_LG, pady=(0, SPACE_LG))
