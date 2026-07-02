"""File chip — selected-file card with icon, caption, filename, meta line
and a right-aligned action row.

Superset of the `_show_chip` blocks in Import ("FILE TERPILIH" + Ganti /
Batal / Konfirmasi) and Export ("TEMPLATE LAPORAN BULANAN" + Ganti /
Preview / Export). Screens keep ONE instance alive and call
set_content(...) on every (re)selection — mirrors the existing pattern of
clearing chip_frame children in _show_chip. Show/hide (pack/pack_forget,
before=...) stays with the caller.
"""
from dataclasses import dataclass
from typing import Callable

import customtkinter as ctk

from src.ui.theme import (
    FONT_FAMILY,
    COLOR_BG, COLOR_SURFACE, COLOR_SURFACE_HIGH,
    COLOR_BORDER, COLOR_BORDER_STRONG,
    COLOR_ACCENT, COLOR_ACCENT_HOVER,
    COLOR_INFO,
    COLOR_TEXT, COLOR_TEXT_DIM, COLOR_TEXT_MUTED, COLOR_TEXT_DISABLED,
    FONT_BODY_BOLD, FONT_LABEL,
    FONT_MONO_DATA, FONT_MONO_SMALL,
    SPACE_XS, SPACE_SM, SPACE_MD,
    RADIUS_MD,
)


@dataclass(frozen=True)
class FileChipAction:
    """One action button on the chip.

    kind:
        "neutral" — outline abu (Ganti / Batal)
        "info"    — outline cyan (Preview)
        "primary" — solid magenta CTA (Konfirmasi / Export)
    """
    text: str
    command: Callable[[], None]
    kind: str = "neutral"
    width: int = 80


class FileChip(ctk.CTkFrame):
    """Selected-file card. Content is (re)built via set_content().

    Args:
        parent: parent widget
        label: uppercase caption, e.g. "FILE TERPILIH"
        filename: main mono line (file name)
        meta: muted mono line, e.g. "120 KB · diparsing dalam 45 ms"
        extra: optional extra mono line in disabled tone, e.g.
            "→ Akan menyimpan sebagai: ..." (Export)
        actions: FileChipAction sequence, rendered left→right; the last
            one is conventionally the primary CTA.

    After each set_content() the created buttons are exposed as
    `self.action_buttons` (same order as `actions`) so callers can wire
    them into a BusyGuard.
    """

    def __init__(
        self, parent, *, label: str = "", filename: str = "",
        meta: str = "", extra: str | None = None,
        actions: tuple | list = (),
    ):
        super().__init__(
            parent, fg_color=COLOR_SURFACE,
            border_width=1, border_color=COLOR_BORDER,
            corner_radius=RADIUS_MD,
        )
        self.action_buttons: list[ctk.CTkButton] = []
        self.set_content(
            label=label, filename=filename, meta=meta,
            extra=extra, actions=actions,
        )

    def set_content(
        self, *, label: str, filename: str, meta: str,
        extra: str | None = None, actions: tuple | list = (),
    ) -> None:
        """Clear and rebuild the chip's children (new file selected)."""
        for w in self.winfo_children():
            w.destroy()
        self.action_buttons = []

        ctk.CTkLabel(
            self, text="📄",
            font=(FONT_FAMILY, 24),
            text_color=COLOR_TEXT,
        ).pack(side="left", padx=(SPACE_MD, SPACE_SM), pady=SPACE_MD)

        info = ctk.CTkFrame(self, fg_color="transparent")
        info.pack(side="left", fill="x", expand=True, pady=SPACE_MD)
        ctk.CTkLabel(
            info, text=label,
            font=FONT_LABEL, text_color=COLOR_TEXT_MUTED,
            anchor="w",
        ).pack(fill="x")
        ctk.CTkLabel(
            info, text=filename,
            font=FONT_MONO_DATA, text_color=COLOR_TEXT,
            anchor="w",
        ).pack(fill="x")
        ctk.CTkLabel(
            info, text=meta,
            font=FONT_MONO_SMALL, text_color=COLOR_TEXT_MUTED,
            anchor="w",
        ).pack(fill="x")
        if extra:
            ctk.CTkLabel(
                info, text=extra,
                font=FONT_MONO_SMALL, text_color=COLOR_TEXT_DISABLED,
                anchor="w",
            ).pack(fill="x", pady=(SPACE_XS, 0))

        if not actions:
            return
        action_row = ctk.CTkFrame(self, fg_color="transparent")
        action_row.pack(side="right", padx=SPACE_MD, pady=SPACE_MD)
        for i, action in enumerate(actions):
            btn = self._build_action_button(action_row, action)
            is_last = (i == len(actions) - 1)
            btn.pack(side="left", padx=(0, 0 if is_last else SPACE_XS))
            self.action_buttons.append(btn)

    @staticmethod
    def _build_action_button(parent, action: FileChipAction) -> ctk.CTkButton:
        if action.kind == "primary":
            return ctk.CTkButton(
                parent, text=action.text, command=action.command,
                fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
                text_color=COLOR_BG,
                font=FONT_BODY_BOLD,
                width=action.width,
            )
        border = COLOR_INFO if action.kind == "info" else COLOR_BORDER_STRONG
        text_color = COLOR_INFO if action.kind == "info" else COLOR_TEXT_DIM
        return ctk.CTkButton(
            parent, text=action.text, command=action.command,
            fg_color="transparent",
            border_width=1, border_color=border,
            text_color=text_color,
            hover_color=COLOR_SURFACE_HIGH,
            font=FONT_BODY_BOLD,
            width=action.width,
        )
