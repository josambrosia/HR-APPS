"""Modal — resolve import-vs-manual conflicts one row at a time.

Shown only when an import would overwrite rows the user hand-edited. Each row
gets a side-by-side diff (Manual vs Import) and a keep/overwrite choice
(default: keep). Bulk buttons set every row at once. Returns a resolution map
{(no_staff, tanggal): "keep"|"take"} to the caller, or None on cancel.
See spec §7.3. Follows the BatchResolveDialog modal skeleton.
"""
from typing import Callable

import customtkinter as ctk

from src.core.import_conflicts import CONFLICT_FIELDS
from src.core.week_utils import MONTH_NAMES_ID, hari_name
from src.ui.theme import (
    COLOR_BG, COLOR_SURFACE, COLOR_SURFACE_HIGH, COLOR_BORDER,
    COLOR_ACCENT, COLOR_ACCENT_HOVER, COLOR_INFO, COLOR_WARN,
    COLOR_TEXT, COLOR_TEXT_DIM, COLOR_TEXT_MUTED,
    FONT_HEADING, FONT_BODY, FONT_BODY_BOLD, FONT_SMALL, FONT_LABEL,
    FONT_MONO_SMALL,
    SPACE_XS, SPACE_SM, SPACE_MD, SPACE_LG, SPACE_XL,
    RADIUS_MD,
)

DIALOG_W = 620
DIALOG_H = 580
_SCREEN_BUFFER = 100

_FIELD_LABEL = {
    "tipe": "tipe", "jadwal": "jadwal", "masuk": "masuk", "keluar": "keluar",
    "kerja_jam": "kerja", "lembur_jam": "lembur", "terlambat_menit": "telat",
}
_KEEP, _TAKE = "Pertahankan", "Pakai import"


def _fmt_tanggal(iso):
    try:
        y, m, d = iso.split("-")
        return f"{hari_name(iso)}, {int(d)} {MONTH_NAMES_ID[int(m)]} {y}"
    except (ValueError, KeyError):
        return iso


def _fmt_val(v):
    return "—" if v in (None, "") else str(v)


def _diff_line(values, changed):
    return "  ·  ".join(f"{_FIELD_LABEL[f]} {_fmt_val(values[f])}" for f in changed) \
        if changed else "—"


class ImportConflictDialog(ctk.CTkToplevel):
    ROW_HEADER, ROW_CONTENT, ROW_FOOTER = 0, 1, 2

    def __init__(self, parent, *, conflicts, file_label, non_conflict_count,
                 on_resolved: Callable):
        super().__init__(parent)
        self._conflicts = conflicts
        self._file_label = file_label
        self._non_conflict = non_conflict_count
        self._on_resolved = on_resolved
        self._vars = {}

        self.title("Konflik Import")
        self.configure(fg_color=COLOR_BG)
        self.resizable(False, False)
        self.transient(parent)

        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        h = min(DIALOG_H, sh - _SCREEN_BUFFER)
        x, y = (sw - DIALOG_W) // 2, max(0, (sh - h) // 2)
        self.geometry(f"{DIALOG_W}x{h}+{x}+{y}")

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(self.ROW_HEADER, weight=0)
        self.grid_rowconfigure(self.ROW_CONTENT, weight=1)
        self.grid_rowconfigure(self.ROW_FOOTER, weight=0)

        self._build()
        self.after(50, lambda: (self.grab_set(), self.focus_set()))
        self.bind("<Escape>", lambda _e: self._cancel())
        self.protocol("WM_DELETE_WINDOW", self._cancel)

    def _build(self):
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=self.ROW_HEADER, column=0, sticky="ew",
                    padx=SPACE_XL, pady=(SPACE_LG, SPACE_SM))
        ctk.CTkLabel(
            header,
            text=f"⚠  Konflik Import — {len(self._conflicts)} baris pernah disunting manual",
            font=FONT_HEADING, text_color=COLOR_TEXT, anchor="w",
        ).pack(anchor="w", fill="x")
        ctk.CTkLabel(
            header,
            text=(f"File {self._file_label} berbeda dari koreksi manualmu. "
                  f"Pilih per baris. {self._non_conflict} baris lain diimpor otomatis."),
            font=FONT_SMALL, text_color=COLOR_TEXT_DIM, anchor="w", justify="left",
        ).pack(anchor="w", fill="x", pady=(SPACE_XS, 0))

        # Bulk row
        bulk = ctk.CTkFrame(header, fg_color="transparent")
        bulk.pack(anchor="w", fill="x", pady=(SPACE_SM, 0))
        ctk.CTkLabel(bulk, text="Terapkan ke semua:", font=FONT_SMALL,
                     text_color=COLOR_TEXT_MUTED).pack(side="left", padx=(0, SPACE_SM))
        ctk.CTkButton(
            bulk, text="Pertahankan manual", command=lambda: self._set_all(_KEEP),
            width=150, height=26, fg_color="transparent", border_width=1,
            border_color=COLOR_INFO, text_color=COLOR_INFO,
            hover_color=COLOR_SURFACE_HIGH, font=FONT_SMALL, corner_radius=RADIUS_MD,
        ).pack(side="left", padx=(0, SPACE_XS))
        ctk.CTkButton(
            bulk, text="Pakai import", command=lambda: self._set_all(_TAKE),
            width=120, height=26, fg_color="transparent", border_width=1,
            border_color=COLOR_WARN, text_color=COLOR_WARN,
            hover_color=COLOR_SURFACE_HIGH, font=FONT_SMALL, corner_radius=RADIUS_MD,
        ).pack(side="left")

        # Footer FIRST (structural)
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=self.ROW_FOOTER, column=0, sticky="ew",
                    padx=SPACE_XL, pady=(SPACE_SM, SPACE_LG))
        ctk.CTkButton(
            footer, text=f"Terapkan & lanjut import", command=self._apply,
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER, text_color=COLOR_BG,
            width=200, height=40, font=FONT_BODY_BOLD, corner_radius=RADIUS_MD,
        ).pack(side="right")
        ctk.CTkButton(
            footer, text="Batal impor", command=self._cancel,
            fg_color="transparent", border_width=1, border_color=COLOR_INFO,
            text_color=COLOR_INFO, hover_color=COLOR_SURFACE_HIGH,
            width=120, height=40, font=FONT_BODY_BOLD, corner_radius=RADIUS_MD,
        ).pack(side="right", padx=(0, SPACE_MD))

        # Scrollable content
        content = ctk.CTkScrollableFrame(self, fg_color="transparent")
        content.grid(row=self.ROW_CONTENT, column=0, sticky="nsew", padx=SPACE_XL)
        for c in self._conflicts:
            self._build_card(content, c)

    def _build_card(self, parent, c):
        card = ctk.CTkFrame(parent, fg_color=COLOR_SURFACE, border_width=1,
                            border_color=COLOR_BORDER, corner_radius=RADIUS_MD)
        card.pack(fill="x", pady=SPACE_XS)

        ctk.CTkLabel(
            card, text=f"{c['nama']}  ·  {_fmt_tanggal(c['tanggal'])}",
            font=FONT_BODY_BOLD, text_color=COLOR_TEXT, anchor="w",
        ).pack(anchor="w", fill="x", padx=SPACE_MD, pady=(SPACE_SM, SPACE_XS))

        changed = c["changed"]
        for tag, color, vals in (("◆ Manual", COLOR_INFO, c["manual"]),
                                 ("↓ Import", COLOR_WARN, c["incoming"])):
            line = ctk.CTkFrame(card, fg_color="transparent")
            line.pack(anchor="w", fill="x", padx=SPACE_MD)
            ctk.CTkLabel(line, text=tag, font=FONT_LABEL, text_color=color,
                         width=70, anchor="w").pack(side="left")
            ctk.CTkLabel(line, text=_diff_line(vals, changed), font=FONT_MONO_SMALL,
                         text_color=COLOR_TEXT, anchor="w", justify="left").pack(
                side="left", fill="x", expand=True)

        var = ctk.StringVar(value=_KEEP)
        self._vars[c["key"]] = var
        seg = ctk.CTkSegmentedButton(
            card, values=[_KEEP, _TAKE], variable=var,
            selected_color=COLOR_ACCENT, selected_hover_color=COLOR_ACCENT_HOVER,
            unselected_color=COLOR_SURFACE_HIGH, unselected_hover_color=COLOR_BORDER,
            text_color=COLOR_TEXT, font=FONT_SMALL,
        )
        seg.pack(anchor="w", padx=SPACE_MD, pady=(SPACE_XS, SPACE_SM))

    def _set_all(self, value):
        for var in self._vars.values():
            var.set(value)

    def _resolution(self):
        return {key: ("keep" if var.get() == _KEEP else "take")
                for key, var in self._vars.items()}

    def _apply(self):
        res = self._resolution()
        self._close()
        self._on_resolved(res)

    def _cancel(self):
        self._close()
        self._on_resolved(None)

    def _close(self):
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()
