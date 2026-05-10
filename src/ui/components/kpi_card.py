import customtkinter as ctk
from src.ui.theme import COLOR_PANEL, FONT_FAMILY


class KPICard(ctk.CTkFrame):
    def __init__(self, parent, label: str, value: str, value_color: str = "#e5e5e5"):
        super().__init__(parent, fg_color=COLOR_PANEL, corner_radius=8)
        ctk.CTkLabel(self, text=label.upper(), font=(FONT_FAMILY, 10),
                     text_color="#94a3b8").pack(anchor="w", padx=14, pady=(12, 0))
        ctk.CTkLabel(self, text=value, font=(FONT_FAMILY, 22, "bold"),
                     text_color=value_color).pack(anchor="w", padx=14, pady=(0, 12))
