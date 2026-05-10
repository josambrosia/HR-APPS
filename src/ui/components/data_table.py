import customtkinter as ctk
from typing import List, Callable, Optional

from src.ui.theme import COLOR_PANEL, FONT_FAMILY


class DataTable(ctk.CTkScrollableFrame):
    """Lightweight scrollable list of rows. Each row is a clickable button.
    Use display_row() to render columns; uses configure_columns to set widths."""

    def __init__(self, parent, columns: List[str], col_widths: List[int],
                 on_row_click: Optional[Callable] = None):
        super().__init__(parent, fg_color=COLOR_PANEL, corner_radius=6)
        self.columns = columns
        self.col_widths = col_widths
        self.on_row_click = on_row_click
        self._render_header()

    def _render_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=8, pady=4)
        for col, w in zip(self.columns, self.col_widths):
            ctk.CTkLabel(header, text=col.upper(), font=(FONT_FAMILY, 10, "bold"),
                         text_color="#94a3b8", width=w, anchor="w").pack(side="left")

    def set_rows(self, rows: List[dict], values_fn: Callable[[dict], List[str]]):
        # Remove existing data rows
        for w in self.winfo_children()[1:]:
            w.destroy()
        for row in rows:
            self._add_row(row, values_fn(row))

    def _add_row(self, row_data: dict, values: List[str]):
        rf = ctk.CTkFrame(self, fg_color="transparent",
                          height=32, corner_radius=4)
        rf.pack(fill="x", padx=8, pady=1)
        for v, w in zip(values, self.col_widths):
            ctk.CTkLabel(rf, text=v, font=(FONT_FAMILY, 12),
                         width=w, anchor="w").pack(side="left")
        if self.on_row_click:
            rf.bind("<Button-1>", lambda e, r=row_data: self.on_row_click(r))
            for child in rf.winfo_children():
                child.bind("<Button-1>", lambda e, r=row_data: self.on_row_click(r))
