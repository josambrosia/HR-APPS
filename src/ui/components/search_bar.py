"""Reusable search input — pill input with placeholder, clear button,
'N dari M' counter. Caller is responsible for the actual filtering
logic; this component only owns the input UI and emits on_change(query)
on every keystroke.
"""
from typing import Callable

import customtkinter as ctk

from src.ui.theme import (
    COLOR_BORDER, COLOR_SURFACE_HIGH,
    COLOR_TEXT, COLOR_TEXT_DIM, COLOR_TEXT_MUTED,
    FONT_BODY, FONT_SMALL,
    SPACE_XS, SPACE_SM,
    RADIUS_MD,
)


class SearchBar(ctk.CTkFrame):
    """Filter input bar with clear button and N-of-M counter.

    Layout: [🔍 input field] [✕] [12 dari 47]

    Caller passes `on_change(query: str)` which is invoked on every
    keystroke with the current query text.
    """

    def __init__(
        self,
        parent,
        on_change: Callable[[str], None],
        placeholder: str = "🔍 Cari karyawan...",
        width: int = 240,
        **kwargs,
    ):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self._on_change = on_change

        self._query_var = ctk.StringVar(value="")
        self._query_var.trace_add("write", self._on_var_change)

        self._entry = ctk.CTkEntry(
            self,
            textvariable=self._query_var,
            placeholder_text=placeholder,
            width=width, height=30,
            fg_color=COLOR_SURFACE_HIGH,
            border_color=COLOR_BORDER, border_width=1,
            text_color=COLOR_TEXT,
            font=FONT_BODY,
            corner_radius=RADIUS_MD,
        )
        self._entry.pack(side="left", padx=(0, SPACE_XS))

        self._clear_btn = ctk.CTkButton(
            self, text="✕", command=self.clear,
            width=28, height=30,
            fg_color="transparent",
            hover_color=COLOR_SURFACE_HIGH,
            text_color=COLOR_TEXT_MUTED,
            border_width=1, border_color=COLOR_BORDER,
            corner_radius=RADIUS_MD,
            font=FONT_SMALL,
        )
        self._clear_btn.pack(side="left", padx=(0, SPACE_SM))

        self._counter_label = ctk.CTkLabel(
            self, text="", font=FONT_SMALL,
            text_color=COLOR_TEXT_DIM,
        )
        self._counter_label.pack(side="left")

    def _on_var_change(self, *_args):
        self._on_change(self.get())

    def get(self) -> str:
        return self._query_var.get()

    def clear(self) -> None:
        self._query_var.set("")  # triggers _on_var_change → on_change("")

    def set_count(self, visible: int, total: int) -> None:
        if total == 0:
            self._counter_label.configure(text="")
        else:
            self._counter_label.configure(text=f"{visible} dari {total}")

    def focus(self) -> None:
        self._entry.focus_set()
