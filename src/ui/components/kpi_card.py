import customtkinter as ctk
from src.ui.theme import (
    COLOR_SURFACE, COLOR_BORDER, COLOR_TEXT, COLOR_TEXT_MUTED,
    FONT_FAMILY, FONT_MONO, FONT_LABEL,
    SPACE_SM, SPACE_MD, SPACE_LG,
    RADIUS_MD,
)


class KPICard(ctk.CTkFrame):
    """Reusable KPI card.

    Args:
        parent: parent widget
        label: uppercase caption above the value
        value: the value string
        value_color: text color for the value
        mono: if True, render value in monospace (good for numeric values).
              Defaults to True since numbers dominate KPI usage.
    """

    def __init__(
        self, parent, label: str, value: str,
        value_color: str = COLOR_TEXT, *, mono: bool = True,
    ):
        super().__init__(
            parent,
            fg_color=COLOR_SURFACE,
            border_width=1,
            border_color=COLOR_BORDER,
            corner_radius=RADIUS_MD,
        )
        ctk.CTkLabel(
            self, text=label.upper(),
            font=FONT_LABEL,
            text_color=COLOR_TEXT_MUTED,
        ).pack(anchor="w", padx=SPACE_LG, pady=(SPACE_MD, 0))
        value_font = (FONT_MONO if mono else FONT_FAMILY, 22, "bold")
        self._value_label = ctk.CTkLabel(
            self, text=value, font=value_font, text_color=value_color,
        )
        self._value_label.pack(anchor="w", padx=SPACE_LG, pady=(0, SPACE_MD))
