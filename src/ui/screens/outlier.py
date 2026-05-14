"""Outlier / Pengecualian screen — manage which employees are excluded
from Dashboard & Coaching analytics for the active month onward.

See spec: docs/superpowers/specs/2026-05-14-outlier-exclusion-design.md
"""
import customtkinter as ctk

from src.config import DB_PATH
from src.core.report_generator import month_label
from src.db.connection import get_connection
from src.db.settings import get_setting
from src.db.outlier import (
    month_roster, list_active_exclusions,
    exclude_employee, revert_employee, revert_all,
)
from src.ui.theme import (
    COLOR_BG, COLOR_SURFACE, COLOR_SURFACE_HIGH,
    COLOR_BORDER, COLOR_BORDER_STRONG,
    COLOR_ACCENT, COLOR_ACCENT_HOVER,
    COLOR_INFO, COLOR_SECONDARY,
    COLOR_TEXT, COLOR_TEXT_DIM, COLOR_TEXT_MUTED,
    FONT_DISPLAY, FONT_SUBHEAD, FONT_BODY_BOLD,
    FONT_SMALL, FONT_LABEL, FONT_MONO_SMALL,
    SPACE_XS, SPACE_SM, SPACE_MD, SPACE_LG,
    RADIUS_SM, RADIUS_MD,
)

# Violet-tinted treatment for excluded rows (matches approved mockup)
_EXCLUDED_BG = "#160E1C"
_EXCLUDED_BORDER = "#3A2348"


class OutlierScreen(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        with get_connection(DB_PATH) as conn:
            self._month = get_setting(conn, "current_month") or ""

        self._build_header()
        self._build_scroll()
        self._render()

    # -- layout scaffold --
    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, SPACE_MD))
        left = ctk.CTkFrame(header, fg_color="transparent")
        left.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(
            left, text="Outlier - Pengecualian",
            font=FONT_DISPLAY, text_color=COLOR_TEXT,
        ).pack(anchor="w")
        ctk.CTkLabel(
            left,
            text="Kecualikan karyawan tertentu dari analisis Dashboard & Coaching",
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
                badge, text="BULAN AKTIF", font=FONT_LABEL,
                text_color="#5FB8C8",  # cyan 30% label (matches active-month badge)
            ).pack(anchor="e", padx=SPACE_MD, pady=(SPACE_XS, 0))
            ctk.CTkLabel(
                badge, text=month_label(self._month),
                font=FONT_BODY_BOLD, text_color=COLOR_INFO,
            ).pack(anchor="e", padx=SPACE_MD, pady=(0, SPACE_XS))

    def _build_scroll(self):
        self.scroll = ctk.CTkScrollableFrame(self, fg_color=COLOR_BG)
        self.scroll.grid(row=1, column=0, sticky="nsew")

    # -- render --
    def _render(self):
        for child in self.scroll.winfo_children():
            child.destroy()

        if not self._month:
            self._render_empty(
                "Belum ada bulan aktif.",
                "Pilih bulan di menu Active Month dulu.",
            )
            return

        with get_connection(DB_PATH) as conn:
            roster = month_roster(conn, self._month)
            active = list_active_exclusions(conn)

        if not roster:
            self._render_empty(
                "Belum ada data untuk bulan aktif.",
                "Import fingerprint dulu via menu Import.",
            )
            return

        excluded_ids = {a["employee_id"] for a in active}
        active_by_id = {a["employee_id"]: a for a in active}
        excluded_rows = [r for r in roster if r["id"] in excluded_ids]
        included_rows = [r for r in roster if r["id"] not in excluded_ids]

        self._render_infobar(len(excluded_rows), len(roster))

        if excluded_rows:
            self._render_section_label(
                "Dikecualikan", len(excluded_rows), excluded=True,
            )
            for r in excluded_rows:
                self._render_row(
                    r, excluded=True,
                    since=active_by_id[r["id"]]["effective_from"],
                )

        self._render_section_label(
            "Disertakan dalam analisis", len(included_rows), excluded=False,
        )
        for r in included_rows:
            self._render_row(r, excluded=False, since=None)

        if excluded_rows:
            self._render_footer(len(excluded_rows))

    def _render_empty(self, title: str, hint: str):
        box = ctk.CTkFrame(
            self.scroll, fg_color=COLOR_SURFACE,
            border_width=1, border_color=COLOR_BORDER,
            corner_radius=RADIUS_MD,
        )
        box.pack(fill="x", pady=SPACE_SM, padx=SPACE_XS)
        ctk.CTkLabel(
            box, text=title, font=FONT_SUBHEAD, text_color=COLOR_TEXT,
        ).pack(anchor="w", padx=SPACE_LG, pady=(SPACE_LG, SPACE_XS))
        ctk.CTkLabel(
            box, text=hint, font=FONT_SMALL, text_color=COLOR_TEXT_DIM,
        ).pack(anchor="w", padx=SPACE_LG, pady=(0, SPACE_LG))

    def _render_infobar(self, excluded_count: int, total: int):
        bar = ctk.CTkFrame(
            self.scroll, fg_color=COLOR_SURFACE,
            border_width=1, border_color=COLOR_BORDER,
            corner_radius=RADIUS_MD,
        )
        bar.pack(fill="x", pady=(SPACE_XS, SPACE_MD), padx=SPACE_XS)
        msg = (
            f"{excluded_count} dari {total} karyawan dikecualikan dari "
            f"analisis bulan ini. Pengecualian hanya memengaruhi angka "
            f"Dashboard & Coaching - issue mereka tetap terbuka dan harus "
            f"di-resolve seperti biasa."
        )
        ctk.CTkLabel(
            bar, text=msg, font=FONT_SMALL, text_color=COLOR_TEXT_DIM,
            wraplength=720, justify="left", anchor="w",
        ).pack(anchor="w", fill="x", padx=SPACE_MD, pady=SPACE_SM)

    def _render_section_label(self, text: str, count: int, excluded: bool):
        row = ctk.CTkFrame(self.scroll, fg_color="transparent")
        row.pack(fill="x", padx=SPACE_XS, pady=(SPACE_MD, SPACE_XS))
        ctk.CTkLabel(
            row, text=text.upper(), font=FONT_LABEL,
            text_color=COLOR_SECONDARY if excluded else COLOR_TEXT_MUTED,
        ).pack(side="left")
        ctk.CTkLabel(
            row, text=f"  {count}", font=FONT_LABEL,
            text_color=COLOR_TEXT_MUTED,
        ).pack(side="left")

    def _render_row(self, emp: dict, excluded: bool, since):
        card = ctk.CTkFrame(
            self.scroll,
            fg_color=_EXCLUDED_BG if excluded else COLOR_SURFACE,
            border_width=1,
            border_color=_EXCLUDED_BORDER if excluded else COLOR_BORDER,
            corner_radius=RADIUS_MD,
        )
        card.pack(fill="x", pady=2, padx=SPACE_XS)

        ctk.CTkLabel(
            card, text=emp["nama"][:1].upper(),
            font=FONT_BODY_BOLD,
            text_color=COLOR_SECONDARY if excluded else COLOR_TEXT_MUTED,
            fg_color=COLOR_SURFACE_HIGH, corner_radius=RADIUS_SM,
            width=30, height=30,
        ).pack(side="left", padx=(SPACE_MD, SPACE_SM), pady=SPACE_SM)

        info = ctk.CTkFrame(card, fg_color="transparent")
        info.pack(side="left", fill="x", expand=True, pady=SPACE_SM)
        ctk.CTkLabel(
            info, text=emp["nama"], font=FONT_BODY_BOLD,
            text_color=COLOR_TEXT,
        ).pack(anchor="w")
        meta = emp["dept"] or "-"
        if excluded and since:
            meta = f"{meta} - sejak {month_label(since)}"
        ctk.CTkLabel(
            info, text=meta, font=FONT_MONO_SMALL,
            text_color=COLOR_TEXT_MUTED,
        ).pack(anchor="w")

        if excluded:
            ctk.CTkButton(
                card, text="Sertakan kembali", width=150, height=30,
                fg_color="transparent",
                border_width=1, border_color=COLOR_SECONDARY,
                text_color=COLOR_SECONDARY, hover_color=COLOR_SURFACE_HIGH,
                font=FONT_SMALL,
                command=lambda eid=emp["id"]: self._on_revert(eid),
            ).pack(side="right", padx=SPACE_MD, pady=SPACE_SM)
        else:
            ctk.CTkButton(
                card, text="Kecualikan", width=110, height=30,
                fg_color="transparent",
                border_width=1, border_color=COLOR_BORDER_STRONG,
                text_color=COLOR_TEXT_DIM, hover_color=COLOR_SURFACE_HIGH,
                font=FONT_SMALL,
                command=lambda eid=emp["id"]: self._on_exclude(eid),
            ).pack(side="right", padx=SPACE_MD, pady=SPACE_SM)

    def _render_footer(self, excluded_count: int):
        footer = ctk.CTkFrame(self.scroll, fg_color="transparent")
        footer.pack(fill="x", pady=(SPACE_MD, SPACE_SM), padx=SPACE_XS)
        ctk.CTkButton(
            footer, text=f"Revert Semua ({excluded_count})",
            width=170, height=34,
            fg_color="transparent",
            border_width=1, border_color=COLOR_BORDER,
            text_color=COLOR_TEXT_MUTED, hover_color=COLOR_SURFACE_HIGH,
            font=FONT_SMALL,
            command=self._on_revert_all,
        ).pack(side="right")

    # -- actions --
    def _on_exclude(self, employee_id: int):
        with get_connection(DB_PATH) as conn:
            exclude_employee(conn, employee_id, self._month)
            conn.commit()
        self._render()

    def _on_revert(self, employee_id: int):
        with get_connection(DB_PATH) as conn:
            revert_employee(conn, employee_id, self._month)
            conn.commit()
        self._render()

    def _on_revert_all(self):
        with get_connection(DB_PATH) as conn:
            revert_all(conn, self._month)
            conn.commit()
        self._render()
