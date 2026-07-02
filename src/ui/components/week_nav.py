"""Reusable week-navigation bar used by Issues and Dashboard screens.

Renders pills: [Semua] [Minggu 1 (01-07)] [Minggu 2 (08-14)] ...

Active pill uses magenta fill; inactive pills have a subtle border
on a transparent background. Calls back when user clicks a different pill.
"""
from typing import Callable, Dict, Optional

import customtkinter as ctk

from src.core.week_utils import weeks_in_month
from src.ui.theme import (
    COLOR_ACCENT, COLOR_BG, COLOR_BORDER, COLOR_SURFACE_HIGH,
    COLOR_TEXT_DIM, FONT_SMALL,
)


class WeekNavBar(ctk.CTkFrame):
    """A horizontal bar of pill buttons: Semua | Minggu 1 | Minggu 2 | ...

    The caller passes `on_change(key)` which is invoked with one of:
      - "semua"
      - "minggu_1", "minggu_2", ...
    """

    def __init__(
        self,
        parent,
        current_month: str,
        on_change: Callable[[str], None],
        initial: str = "semua",
        include_all: bool = True,
    ):
        super().__init__(parent, fg_color="transparent")
        self._on_change = on_change
        self._buttons: Dict[str, ctk.CTkButton] = {}
        self._active = initial
        self._month = current_month
        self._include_all = include_all

        self._build_pills()

        # If the requested initial isn't actually rendered (e.g., "semua" with
        # include_all=False), fall back to the first available pill.
        if self._active not in self._buttons and self._buttons:
            self._active = next(iter(self._buttons.keys()))

        self._refresh_styles()

    def _build_pills(self):
        if self._include_all:
            self._make_pill("semua", "Semua")
        if self._month:
            for num, start, end in weeks_in_month(self._month):
                s_day = start.split("-")[2]
                e_day = end.split("-")[2]
                self._make_pill(f"minggu_{num}", f"Minggu {num} ({s_day}-{e_day})")

    def _make_pill(self, key: str, label: str):
        btn = ctk.CTkButton(
            self, text=label,
            command=lambda k=key: self._on_click(k),
            fg_color="transparent",
            hover_color=COLOR_SURFACE_HIGH,
            corner_radius=14, height=30,
            border_width=1, border_color=COLOR_BORDER,
            text_color=COLOR_TEXT_DIM,
            font=FONT_SMALL,
        )
        btn.pack(side="left", padx=4)
        self._buttons[key] = btn

    def _on_click(self, key: str):
        if key == self._active:
            return
        self._active = key
        self._refresh_styles()
        self._on_change(key)

    def _refresh_styles(self):
        for key, btn in self._buttons.items():
            if key == self._active:
                btn.configure(
                    fg_color=COLOR_ACCENT,
                    text_color=COLOR_BG,   # dark text on bright magenta for contrast
                    border_color=COLOR_ACCENT,
                )
            else:
                btn.configure(
                    fg_color="transparent",
                    text_color=COLOR_TEXT_DIM,
                    border_color=COLOR_BORDER,
                )

    def set_active(self, key: str):
        if key not in self._buttons:
            return
        self._active = key
        self._refresh_styles()

    def sync(self, current_month: str, active: Optional[str] = None):
        """Re-sync a persistent (cached-screen) bar without firing on_change.

        Rebuilds the pills when the active month changed (week count/labels
        depend on it), then re-applies `active` with the same fallback rule
        as __init__ (missing key → first rendered pill). Screens call this
        from on_show() so a cached WeekNavBar tracks the session week
        (core.session_state.period_state) and month changes made elsewhere.
        Callers should read `.active` back afterward instead of assuming
        the requested key survived the fallback."""
        if current_month != self._month:
            self._month = current_month
            for btn in self._buttons.values():
                btn.destroy()
            self._buttons = {}
            self._build_pills()
        if active is not None:
            self._active = active
        if self._active not in self._buttons and self._buttons:
            self._active = next(iter(self._buttons.keys()))
        self._refresh_styles()

    @property
    def active(self) -> str:
        return self._active
