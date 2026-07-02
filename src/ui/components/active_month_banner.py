"""Active-month banner / badge — the cyan info tint shared by 4 screens.

Two variants of the same component:

  variant="banner" — full-width strip (icon + text), used at the top of
      Import and Export. State togglable after construction:
      set_info(text) → cyan tint + 📆 icon (default), set_warn(text) →
      rose tint + ⚠ icon (month-mismatch warnings).

  variant="badge" — compact right-aligned chip ("BULAN AKTIF" caption +
      month value), used in the Outlier and Hari Libur headers.

The caller packs/grids the component itself and supplies all text —
this component owns only the visual treatment. Extra trailing widgets
(if ever needed) can be packed onto the component directly with
side="right"; `hint=` covers the simple muted-text case.
"""
import customtkinter as ctk

from src.ui.theme import (
    FONT_FAMILY,
    COLOR_INFO, COLOR_WARN,
    COLOR_INFO_TINT_BG, COLOR_INFO_TINT_BORDER, COLOR_INFO_TINT_TEXT,
    COLOR_WARN_TINT_BG, COLOR_WARN_TINT_BORDER,
    COLOR_TEXT, COLOR_TEXT_MUTED,
    FONT_BODY, FONT_BODY_BOLD, FONT_SMALL, FONT_LABEL,
    SPACE_XS, SPACE_SM, SPACE_MD,
    RADIUS_SM, RADIUS_MD,
)


class ActiveMonthBanner(ctk.CTkFrame):
    """Cyan active-month strip (banner) or chip (badge).

    Args:
        parent: parent widget
        variant: "banner" (full-width info strip) or "badge" (compact chip)
        text: body text — banner variant only
        label: uppercase caption — badge variant only (default "BULAN AKTIF")
        value: value line under the caption — badge variant only
        hint: optional muted trailing text on the right — banner variant only
    """

    def __init__(
        self, parent, *, variant: str = "banner",
        text: str = "", label: str = "BULAN AKTIF", value: str = "",
        hint: str | None = None,
    ):
        if variant not in ("banner", "badge"):
            raise ValueError(f"variant tidak dikenal: {variant!r}")
        self._variant = variant
        super().__init__(
            parent,
            fg_color=COLOR_INFO_TINT_BG,
            border_width=1, border_color=COLOR_INFO_TINT_BORDER,
            corner_radius=RADIUS_MD if variant == "banner" else RADIUS_SM,
        )
        if variant == "banner":
            self._build_banner(text, hint)
        else:
            self._build_badge(label, value)

    # -- banner variant --
    def _build_banner(self, text: str, hint: str | None):
        self.icon_label = ctk.CTkLabel(
            self, text="📆",
            font=(FONT_FAMILY, 16),
            text_color=COLOR_INFO,
        )
        self.icon_label.pack(side="left", padx=(SPACE_MD, SPACE_SM), pady=SPACE_SM)
        # Optional trailing hint packs BEFORE the expanding text label so it
        # keeps its right-edge slot while the text absorbs the leftover width.
        if hint:
            ctk.CTkLabel(
                self, text=hint,
                font=FONT_SMALL, text_color=COLOR_TEXT_MUTED,
                anchor="e",
            ).pack(side="right", padx=(SPACE_SM, SPACE_MD), pady=SPACE_SM)
        self.text_label = ctk.CTkLabel(
            self, text=text,
            font=FONT_BODY,
            text_color=COLOR_TEXT,
            anchor="w", justify="left",
        )
        self.text_label.pack(side="left", fill="x", expand=True, pady=SPACE_SM)

    def set_info(self, text: str, icon: str = "📆") -> None:
        """Cyan info state (default) — banner variant only."""
        self.configure(
            fg_color=COLOR_INFO_TINT_BG, border_color=COLOR_INFO_TINT_BORDER,
        )
        self.icon_label.configure(text=icon, text_color=COLOR_INFO)
        self.text_label.configure(text=text)

    def set_warn(self, text: str, icon: str = "⚠") -> None:
        """Rose warning state (e.g. bulan-mismatch) — banner variant only."""
        self.configure(
            fg_color=COLOR_WARN_TINT_BG, border_color=COLOR_WARN_TINT_BORDER,
        )
        self.icon_label.configure(text=icon, text_color=COLOR_WARN)
        self.text_label.configure(text=text)

    # -- badge variant --
    def _build_badge(self, label: str, value: str):
        ctk.CTkLabel(
            self, text=label, font=FONT_LABEL,
            text_color=COLOR_INFO_TINT_TEXT,
        ).pack(anchor="e", padx=SPACE_MD, pady=(SPACE_XS, 0))
        self.value_label = ctk.CTkLabel(
            self, text=value,
            font=FONT_BODY_BOLD, text_color=COLOR_INFO,
        )
        self.value_label.pack(anchor="e", padx=SPACE_MD, pady=(0, SPACE_XS))

    def set_value(self, value: str) -> None:
        """Update the month value — badge variant only."""
        self.value_label.configure(text=value)
