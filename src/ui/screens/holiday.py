"""Hari Libur screen — mark dates in the active month as holidays.

Pola B: multi-select checkboxes + impact preview + Terapkan button.
See spec: docs/superpowers/specs/2026-05-14-hari-libur-and-weekly-export-design.md
"""
import customtkinter as ctk

from src.config import DB_PATH
from src.core.report_generator import month_label
from src.db.connection import get_connection
from src.db.settings import get_setting
from src.db.holidays import workday_roster, mark_holidays, unmark_holidays
from src.ui.components.toast import show_success_toast
from src.ui.theme import (
    COLOR_BG, COLOR_SURFACE,
    COLOR_BORDER,
    COLOR_ACCENT, COLOR_ACCENT_HOVER, COLOR_INFO, COLOR_SECONDARY,
    COLOR_TEXT, COLOR_TEXT_DIM,
    FONT_DISPLAY, FONT_SUBHEAD, FONT_BODY, FONT_BODY_BOLD,
    FONT_SMALL, FONT_LABEL,
    SPACE_XS, SPACE_SM, SPACE_MD, SPACE_LG,
    RADIUS_SM, RADIUS_MD,
)

_MONTH_ID = {
    1: "Januari", 2: "Februari", 3: "Maret", 4: "April", 5: "Mei", 6: "Juni",
    7: "Juli", 8: "Agustus", 9: "September", 10: "Oktober",
    11: "November", 12: "Desember",
}

# Violet-tinted treatment for already-holiday rows (matches Outlier screen)
_HOLIDAY_BG = "#160E1C"
_HOLIDAY_BORDER = "#3A2348"


def _format_tanggal(iso: str, hari: str) -> str:
    """'2026-04-03', 'Jumat' -> 'Jumat, 3 April 2026'."""
    y, m, d = iso.split("-")
    label = f"{int(d)} {_MONTH_ID[int(m)]} {y}"
    return f"{hari}, {label}" if hari else label


class HolidayScreen(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        with get_connection(DB_PATH) as conn:
            self._month = get_setting(conn, "current_month") or ""

        # tanggal -> {"var": BooleanVar, "was_holiday": bool, "issue_count": int}
        self._rows: dict = {}

        self._build_header()
        self._build_scroll()
        self._build_footer()
        self._render()

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, SPACE_MD))
        left = ctk.CTkFrame(header, fg_color="transparent")
        left.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(
            left, text="Hari Libur", font=FONT_DISPLAY, text_color=COLOR_TEXT,
        ).pack(anchor="w")
        ctk.CTkLabel(
            left,
            text="Tandai tanggal sebagai hari libur - tidak dihitung sebagai hari kerja",
            font=FONT_SMALL, text_color=COLOR_TEXT_DIM,
        ).pack(anchor="w", pady=(2, 0))
        if self._month:
            badge = ctk.CTkFrame(
                header, fg_color="#08222B",
                border_width=1, border_color="#12454F",
                corner_radius=RADIUS_SM,
            )
            badge.pack(side="right")
            ctk.CTkLabel(
                badge, text="BULAN AKTIF", font=FONT_LABEL, text_color="#5FB8C8",
            ).pack(anchor="e", padx=SPACE_MD, pady=(SPACE_XS, 0))
            ctk.CTkLabel(
                badge, text=month_label(self._month),
                font=FONT_BODY_BOLD, text_color=COLOR_INFO,
            ).pack(anchor="e", padx=SPACE_MD, pady=(0, SPACE_XS))

    def _build_scroll(self):
        self.scroll = ctk.CTkScrollableFrame(self, fg_color=COLOR_BG)
        self.scroll.grid(row=1, column=0, sticky="nsew")

    def _build_footer(self):
        self.footer = ctk.CTkFrame(self, fg_color="transparent")
        self.footer.grid(row=2, column=0, sticky="ew", pady=(SPACE_MD, 0))
        self._preview_label = ctk.CTkLabel(
            self.footer, text="", font=FONT_SMALL,
            text_color=COLOR_TEXT_DIM, anchor="w", justify="left",
        )
        self._preview_label.pack(side="left", fill="x", expand=True)
        self._apply_btn = ctk.CTkButton(
            self.footer, text="Terapkan Perubahan", width=180, height=34,
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
            text_color=COLOR_BG, font=FONT_BODY_BOLD,
            command=self._on_apply, state="disabled",
        )
        self._apply_btn.pack(side="right")

    def _render(self):
        for child in self.scroll.winfo_children():
            child.destroy()
        self._rows.clear()

        if not self._month:
            self._render_empty(
                "Belum ada bulan aktif.",
                "Pilih bulan di menu Active Month dulu.",
            )
            self.footer.grid_remove()
            return

        with get_connection(DB_PATH) as conn:
            roster = workday_roster(conn, self._month)

        if not roster:
            self._render_empty(
                "Belum ada data untuk bulan aktif.",
                "Import fingerprint dulu via menu Import.",
            )
            self.footer.grid_remove()
            return

        self.footer.grid()
        marked = sum(1 for r in roster if r["is_holiday"])
        self._render_infobar(marked)
        for r in roster:
            self._render_row(r)
        self._update_preview()

    def _render_empty(self, title: str, hint: str):
        box = ctk.CTkFrame(
            self.scroll, fg_color=COLOR_SURFACE,
            border_width=1, border_color=COLOR_BORDER, corner_radius=RADIUS_MD,
        )
        box.pack(fill="x", pady=SPACE_SM, padx=SPACE_XS)
        ctk.CTkLabel(box, text=title, font=FONT_SUBHEAD, text_color=COLOR_TEXT).pack(
            anchor="w", padx=SPACE_LG, pady=(SPACE_LG, SPACE_XS))
        ctk.CTkLabel(box, text=hint, font=FONT_SMALL, text_color=COLOR_TEXT_DIM).pack(
            anchor="w", padx=SPACE_LG, pady=(0, SPACE_LG))

    def _render_infobar(self, marked_count: int):
        bar = ctk.CTkFrame(
            self.scroll, fg_color=COLOR_SURFACE,
            border_width=1, border_color=COLOR_BORDER, corner_radius=RADIUS_MD,
        )
        bar.pack(fill="x", pady=(SPACE_XS, SPACE_MD), padx=SPACE_XS)
        msg = (
            f"{marked_count} hari libur ditandai bulan ini. Hari libur tidak "
            f"dihitung sebagai hari kerja - issue karyawan di tanggal itu "
            f"otomatis ter-resolve & keluar dari recap Dashboard + cetak."
        )
        ctk.CTkLabel(
            bar, text=msg, font=FONT_SMALL, text_color=COLOR_TEXT_DIM,
            wraplength=720, justify="left", anchor="w",
        ).pack(anchor="w", fill="x", padx=SPACE_MD, pady=SPACE_SM)

    def _render_row(self, r: dict):
        tanggal = r["tanggal"]
        is_holiday = r["is_holiday"]
        card = ctk.CTkFrame(
            self.scroll,
            fg_color=_HOLIDAY_BG if is_holiday else COLOR_SURFACE,
            border_width=1,
            border_color=_HOLIDAY_BORDER if is_holiday else COLOR_BORDER,
            corner_radius=RADIUS_MD,
        )
        card.pack(fill="x", pady=2, padx=SPACE_XS)

        var = ctk.BooleanVar(value=is_holiday)
        chk = ctk.CTkCheckBox(
            card, text="", width=24, variable=var,
            command=self._update_preview,
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
        )
        chk.pack(side="left", padx=(SPACE_MD, SPACE_SM), pady=SPACE_SM)

        ctk.CTkLabel(
            card, text=_format_tanggal(tanggal, r["hari"]),
            font=FONT_BODY, text_color=COLOR_TEXT, anchor="w",
        ).pack(side="left", fill="x", expand=True, pady=SPACE_SM)

        if is_holiday:
            ctk.CTkLabel(
                card, text="SUDAH LIBUR", font=FONT_LABEL,
                text_color=COLOR_SECONDARY,
            ).pack(side="right", padx=SPACE_MD, pady=SPACE_SM)

        self._rows[tanggal] = {
            "var": var,
            "was_holiday": is_holiday,
            "issue_count": r["issue_count"],
        }

    def _compute_diff(self):
        """Return (to_mark, to_unmark) date lists from current checkbox state."""
        to_mark, to_unmark = [], []
        for tanggal, st in self._rows.items():
            checked = st["var"].get()
            if checked and not st["was_holiday"]:
                to_mark.append(tanggal)
            elif not checked and st["was_holiday"]:
                to_unmark.append(tanggal)
        return to_mark, to_unmark

    def _update_preview(self):
        to_mark, to_unmark = self._compute_diff()
        parts = []
        if to_mark:
            issues = sum(self._rows[d]["issue_count"] for d in to_mark)
            parts.append(
                f"{len(to_mark)} tanggal jadi libur - {issues} issue akan ter-resolve"
            )
        if to_unmark:
            issues = sum(self._rows[d]["issue_count"] for d in to_unmark)
            parts.append(
                f"{len(to_unmark)} tanggal dibuka kembali - {issues} issue dibuka lagi"
            )
        if parts:
            self._preview_label.configure(text="   |   ".join(parts))
            self._apply_btn.configure(state="normal")
        else:
            self._preview_label.configure(text="Belum ada perubahan.")
            self._apply_btn.configure(state="disabled")

    def _on_apply(self):
        to_mark, to_unmark = self._compute_diff()
        if not to_mark and not to_unmark:
            return
        with get_connection(DB_PATH) as conn:
            if to_mark:
                mark_holidays(conn, to_mark)
            if to_unmark:
                unmark_holidays(conn, to_unmark)
            conn.commit()
        show_success_toast(
            self.winfo_toplevel(),
            title="Hari Libur Diperbarui",
            message=(
                f"{len(to_mark)} tanggal ditandai libur, "
                f"{len(to_unmark)} dibuka kembali."
            ),
        )
        self._render()
