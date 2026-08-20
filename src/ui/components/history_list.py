"""History list — bordered surface with uppercase header + rows of
time / (optional tag) / title / (optional badge).

Superset of `_render_history` in Import ("RIWAYAT IMPORT TERAKHIR":
time · filename · "✓ N emp" badge) and Export ("RIWAYAT EXPORT
TERAKHIR": time · kind tag · filename · "f/t" badge). Screens keep one
instance and call set_rows(...) after every DB write — mirrors the
existing clear-children-and-repopulate pattern.

Per-callsite config:
    Import → rows without `tag`; badge_width 70 (default).
    Export → rows with `tag` (Isi Template / Generate ...); badge_width 80,
             badge_color/badge_bg switched on full vs partial result.
"""
from dataclasses import dataclass

import customtkinter as ctk

from src.ui import motion
from src.ui.theme import (
    COLOR_SURFACE, COLOR_BORDER,
    COLOR_SUCCESS_TINT_BG,
    COLOR_TEXT, COLOR_TEXT_DIM, COLOR_TEXT_MUTED,
    FONT_BODY, FONT_LABEL,
    FONT_MONO_DATA, FONT_MONO_SMALL,
    SPACE_XS, SPACE_SM, SPACE_MD,
    RADIUS_SM, RADIUS_MD,
)


@dataclass(frozen=True)
class HistoryRow:
    """One row in the list. Only `time` and `title` are mandatory."""
    time: str                              # left column, e.g. "Hari ini 08:19"
    title: str                             # expanding mono column (file name)
    tag: str | None = None                 # optional kind column (Export)
    badge_text: str = ""                   # right badge; "" = no badge
    badge_color: str = COLOR_TEXT_DIM
    badge_bg: str = COLOR_SUCCESS_TINT_BG
    badge_width: int = 70


class HistoryList(ctk.CTkFrame):
    """Recent-activity list card.

    Args:
        parent: parent widget
        header: uppercase caption, e.g. "RIWAYAT IMPORT TERAKHIR"
        empty_text: shown when set_rows([]) — e.g. "(belum ada riwayat impor)"
        tag_width: fixed width of the optional tag column (Export uses 140)
    """

    def __init__(
        self, parent, *, header: str, empty_text: str, tag_width: int = 140,
    ):
        super().__init__(
            parent, fg_color=COLOR_SURFACE,
            border_width=1, border_color=COLOR_BORDER,
            corner_radius=RADIUS_MD,
        )
        self._header = header
        self._empty_text = empty_text
        self._tag_width = tag_width
        self._first_row = None
        self.set_rows([])

    def set_rows(self, rows: list, *, flash_first: bool = False) -> None:
        """Clear and re-render the whole list (rows: list[HistoryRow]).

        `flash_first=True` mengilatkan baris teratas — dipakai saat rebuild
        dipicu oleh aksi user (import/export baru selesai), supaya hasil
        kerjanya tidak muncul sebagai baris yang tampak identik dengan yang
        lama. JANGAN dinyalakan saat rebuild dipicu on_show/inisialisasi.
        """
        for w in self.winfo_children():
            w.destroy()
        self._first_row = None

        ctk.CTkLabel(
            self, text=self._header,
            font=FONT_LABEL, text_color=COLOR_TEXT_MUTED,
            anchor="w",
        ).pack(fill="x", padx=SPACE_MD, pady=(SPACE_SM, SPACE_XS))

        if not rows:
            ctk.CTkLabel(
                self, text=self._empty_text,
                font=FONT_BODY, text_color=COLOR_TEXT_MUTED,
                anchor="w",
            ).pack(fill="x", padx=SPACE_MD, pady=(0, SPACE_SM))
            return

        for i, r in enumerate(rows):
            row = self._render_row(r)
            if i == 0:
                self._first_row = row
        ctk.CTkFrame(self, fg_color="transparent", height=SPACE_SM).pack()

        if flash_first and self._first_row is not None:
            motion.flash_widget(self._first_row, COLOR_SUCCESS_TINT_BG, COLOR_SURFACE)

    def _render_row(self, r: HistoryRow) -> ctk.CTkFrame:
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=SPACE_MD, pady=2)
        ctk.CTkLabel(
            row, text=r.time,
            font=FONT_MONO_SMALL, text_color=COLOR_TEXT_MUTED,
            anchor="w", width=120,
        ).pack(side="left")
        if r.tag is not None:
            ctk.CTkLabel(
                row, text=r.tag,
                font=FONT_LABEL, text_color=COLOR_TEXT_DIM,
                anchor="w", width=self._tag_width,
            ).pack(side="left", padx=(SPACE_SM, 0))
        ctk.CTkLabel(
            row, text=r.title,
            font=FONT_MONO_DATA, text_color=COLOR_TEXT,
            anchor="w",
        ).pack(side="left", fill="x", expand=True, padx=(SPACE_SM, SPACE_SM))
        if r.badge_text:
            ctk.CTkLabel(
                row, text=r.badge_text,
                font=FONT_MONO_SMALL, text_color=r.badge_color,
                fg_color=r.badge_bg, corner_radius=RADIUS_SM,
                anchor="e", width=r.badge_width,
            ).pack(side="right")
        return row
