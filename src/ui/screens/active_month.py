"""Active Month screen — list all months in DB with stats and per-month actions."""
import customtkinter as ctk

from src.config import DB_PATH
from src.core.report_generator import month_label
from src.db.attendance import list_months_with_stats
from src.db.connection import get_connection
from src.db.settings import get_setting, set_setting
from src.ui.theme import (
    COLOR_BG, COLOR_SURFACE,
    COLOR_BORDER,
    COLOR_ACCENT, COLOR_ACCENT_HOVER,
    COLOR_SUCCESS,
    COLOR_TEXT, COLOR_TEXT_DIM, COLOR_TEXT_MUTED,
    FONT_DISPLAY, FONT_SUBHEAD,
    FONT_BODY_BOLD, FONT_SMALL,
    FONT_MONO_SMALL,
    SPACE_XS, SPACE_SM, SPACE_MD, SPACE_LG,
    RADIUS_SM, RADIUS_MD,
)


class ActiveMonthScreen(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        with get_connection(DB_PATH) as conn:
            self._current_month = get_setting(conn, "current_month") or ""

        self._build_header()
        self._build_list()

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, SPACE_LG))
        ctk.CTkLabel(
            header, text="Pilih Bulan Aktif",
            font=FONT_DISPLAY,
            text_color=COLOR_TEXT,
        ).pack(side="left")

    def _build_list(self):
        # Scroll area uses COLOR_BG (matches app bg, no purple panel)
        self.scroll = ctk.CTkScrollableFrame(
            self, fg_color=COLOR_BG, corner_radius=RADIUS_MD,
        )
        self.scroll.grid(row=1, column=0, sticky="nsew")
        self._render_cards()

    def _render_cards(self):
        for child in self.scroll.winfo_children():
            child.destroy()

        with get_connection(DB_PATH) as conn:
            months = [dict(r) for r in list_months_with_stats(conn)]

        if not months:
            self._render_empty_state()
            return

        for m in months:
            self._render_card(m)

    def _render_empty_state(self):
        empty = ctk.CTkFrame(
            self.scroll, fg_color=COLOR_SURFACE,
            border_width=1, border_color=COLOR_BORDER,
            corner_radius=RADIUS_MD,
        )
        empty.pack(fill="x", pady=SPACE_SM, padx=SPACE_XS)
        ctk.CTkLabel(
            empty, text="Belum ada data.",
            font=FONT_SUBHEAD, text_color=COLOR_TEXT,
        ).pack(anchor="w", padx=SPACE_LG, pady=(SPACE_LG, SPACE_XS))
        ctk.CTkLabel(
            empty, text="Import fingerprint dulu via menu Import.",
            font=FONT_SMALL, text_color=COLOR_TEXT_DIM,
        ).pack(anchor="w", padx=SPACE_LG, pady=(0, SPACE_LG))

    def _render_card(self, m: dict):
        is_active = m["year_month"] == self._current_month

        # Card construction with semantic border
        border_color = COLOR_ACCENT if is_active else COLOR_BORDER
        card = ctk.CTkFrame(
            self.scroll, fg_color=COLOR_SURFACE,
            border_width=1, border_color=border_color,
            corner_radius=RADIUS_MD,
        )
        card.pack(fill="x", pady=SPACE_XS, padx=SPACE_XS)

        # ── Title row: month name + AKTIF badge on right (if active) ──
        title_row = ctk.CTkFrame(card, fg_color="transparent")
        title_row.pack(fill="x", padx=SPACE_LG, pady=(SPACE_MD, SPACE_XS))
        ctk.CTkLabel(
            title_row, text=month_label(m["year_month"]),
            font=FONT_SUBHEAD, text_color=COLOR_TEXT,
        ).pack(side="left")
        if is_active:
            # Solid magenta pill badge — readable from across the screen
            ctk.CTkLabel(
                title_row, text=" AKTIF ",
                font=FONT_MONO_SMALL,
                text_color=COLOR_BG,
                fg_color=COLOR_ACCENT,
                corner_radius=RADIUS_SM,
            ).pack(side="right")

        # ── Stats line (mono small + muted) ──
        stats = (f"{m['hari_count']} hari · "
                 f"{m['records_count']} records · "
                 f"{m['open_issues_count']} issue open")
        ctk.CTkLabel(
            card, text=stats,
            font=FONT_MONO_SMALL, text_color=COLOR_TEXT_MUTED,
        ).pack(anchor="w", padx=SPACE_LG, pady=(0, SPACE_SM))

        # ── Buttons row ──
        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(fill="x", padx=SPACE_MD, pady=(0, SPACE_MD))
        if is_active:
            # Active: emerald disabled-style "Sedang Aktif"
            ctk.CTkButton(
                btn_row, text="✓ Sedang Aktif", width=160,
                fg_color="transparent",
                border_width=1, border_color=COLOR_SUCCESS,
                text_color=COLOR_SUCCESS,
                font=FONT_BODY_BOLD,
                state="disabled",
            ).pack(side="left", padx=SPACE_XS)
        else:
            # Inactive: magenta primary Pilih
            ctk.CTkButton(
                btn_row, text="✓ Pilih", width=100,
                fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
                text_color=COLOR_BG,
                font=FONT_BODY_BOLD,
                command=lambda ym=m["year_month"]: self._on_pick(ym),
            ).pack(side="left", padx=SPACE_XS)

    def _on_pick(self, year_month: str):
        """Make this month the active one + navigate to Dashboard."""
        with get_connection(DB_PATH) as conn:
            set_setting(conn, "current_month", year_month)
        self._current_month = year_month
        # Navigate to Dashboard. HRApp._show is the private nav method;
        # acceptable to call from a child screen as a back-pointer.
        top = self.winfo_toplevel()
        if hasattr(top, "_show"):
            top._show("Dashboard")
