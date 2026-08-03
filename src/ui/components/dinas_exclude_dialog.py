"""Dialog 'Kelola Pengecualian' — sembunyikan pegawai dari Rekap Dinas Paparan.

Centang = disembunyikan. Pengecualian ini hanya berlaku di layar Rekap Dinas
Paparan; Dashboard, Heatmap, dan Coaching tidak terpengaruh. Mengikuti pola
modal BatchResolveDialog (transient + grab_set tertunda + Escape/Return).
"""
from typing import Callable

import customtkinter as ctk

from src.config import DB_PATH
from src.db.connection import get_connection
from src.db.dinas_exclusions import list_employees_with_exclusion, set_excluded_ids
from src.ui.theme import (
    COLOR_BG, COLOR_SURFACE, COLOR_SURFACE_HIGH, COLOR_BORDER,
    COLOR_ACCENT, COLOR_ACCENT_HOVER, COLOR_INFO,
    COLOR_TEXT, COLOR_TEXT_DIM, COLOR_TEXT_MUTED, COLOR_TEXT_DISABLED,
    FONT_HEADING, FONT_BODY, FONT_BODY_BOLD, FONT_SMALL, FONT_MONO_SMALL,
    SPACE_XS, SPACE_SM, SPACE_MD, SPACE_LG, RADIUS_MD,
)

DIALOG_W = 460
DIALOG_H = 560


class DinasExcludeDialog(ctk.CTkToplevel):
    def __init__(self, parent, *, on_saved: Callable[[], None]):
        super().__init__(parent)
        self._on_saved = on_saved

        with get_connection(DB_PATH) as conn:
            self._people = list_employees_with_exclusion(conn)

        self.title("Kelola Pengecualian")
        self.configure(fg_color=COLOR_BG)
        self.transient(parent)
        self.resizable(False, False)

        self._vars = {}
        self._build()

        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{DIALOG_W}x{DIALOG_H}"
                      f"+{(sw - DIALOG_W) // 2}+{max(0, (sh - DIALOG_H) // 2)}")
        self.after(50, lambda: (self.grab_set(), self.focus_set()))
        self.bind("<Escape>", lambda _e: self._close())
        self.bind("<Return>", lambda _e: (self._save(), "break")[1])
        self.protocol("WM_DELETE_WINDOW", self._close)

    # ---------- build ----------
    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=SPACE_LG, pady=(SPACE_LG, SPACE_SM))
        ctk.CTkLabel(head, text="Kelola Pengecualian", font=FONT_HEADING,
                     text_color=COLOR_TEXT, anchor="w").pack(fill="x")
        ctk.CTkLabel(
            head,
            text=("Pegawai yang dicentang disembunyikan dari Rekap Dinas Paparan.\n"
                  "Menu lain (Dashboard, Heatmap, Coaching) tidak terpengaruh."),
            font=FONT_SMALL, text_color=COLOR_TEXT_MUTED, anchor="w",
            justify="left").pack(fill="x", pady=(2, 0))

        self._list = ctk.CTkScrollableFrame(self, fg_color=COLOR_SURFACE,
                                            border_width=1, border_color=COLOR_BORDER,
                                            corner_radius=RADIUS_MD)
        self._list.grid(row=1, column=0, sticky="nsew", padx=SPACE_LG, pady=(0, SPACE_SM))
        self._list.grid_columnconfigure(0, weight=1)

        if not self._people:
            ctk.CTkLabel(self._list, text="Belum ada pegawai aktif.", font=FONT_SMALL,
                         text_color=COLOR_TEXT_MUTED).pack(pady=SPACE_LG)
        for p in self._people:
            var = ctk.BooleanVar(value=p["excluded"])
            self._vars[p["employee_id"]] = var
            row = ctk.CTkFrame(self._list, fg_color="transparent")
            row.pack(fill="x", pady=1)
            ctk.CTkCheckBox(
                row, text=p["nama"], variable=var, font=FONT_BODY,
                text_color=COLOR_TEXT, fg_color=COLOR_ACCENT,
                hover_color=COLOR_ACCENT_HOVER, border_color=COLOR_BORDER,
                checkbox_width=18, checkbox_height=18, corner_radius=4,
            ).pack(side="left", padx=(SPACE_SM, 0))
            if p["dept"]:
                ctk.CTkLabel(row, text=p["dept"], font=FONT_MONO_SMALL,
                             text_color=COLOR_TEXT_DISABLED).pack(side="right",
                                                                  padx=(0, SPACE_SM))

        bulk = ctk.CTkFrame(self, fg_color="transparent")
        bulk.grid(row=2, column=0, sticky="ew", padx=SPACE_LG, pady=(0, SPACE_SM))
        self._count_lbl = ctk.CTkLabel(bulk, text="", font=FONT_MONO_SMALL,
                                       text_color=COLOR_TEXT_DIM)
        self._count_lbl.pack(side="left")
        ctk.CTkButton(bulk, text="Bersihkan semua", command=self._clear_all, width=118,
                      fg_color="transparent", border_width=1, border_color=COLOR_BORDER,
                      text_color=COLOR_TEXT_DIM, hover_color=COLOR_SURFACE_HIGH,
                      font=FONT_SMALL, corner_radius=RADIUS_MD).pack(side="right")
        self._refresh_count()
        for var in self._vars.values():
            var.trace_add("write", lambda *_a: self._refresh_count())

        foot = ctk.CTkFrame(self, fg_color="transparent")
        foot.grid(row=3, column=0, sticky="ew", padx=SPACE_LG, pady=(0, SPACE_LG))
        ctk.CTkButton(foot, text="Simpan", command=self._save, width=110,
                      fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
                      text_color=COLOR_BG, font=FONT_BODY_BOLD,
                      corner_radius=RADIUS_MD).pack(side="right")
        ctk.CTkButton(foot, text="Batal", command=self._close, width=90,
                      fg_color="transparent", border_width=1, border_color=COLOR_INFO,
                      text_color=COLOR_INFO, hover_color=COLOR_SURFACE_HIGH,
                      font=FONT_BODY_BOLD, corner_radius=RADIUS_MD).pack(
            side="right", padx=(0, SPACE_SM))

    # ---------- behavior ----------
    def _selected_ids(self):
        return [eid for eid, var in self._vars.items() if var.get()]

    def _refresh_count(self):
        n = len(self._selected_ids())
        self._count_lbl.configure(
            text="tidak ada yang disembunyikan" if not n
            else f"{n} pegawai disembunyikan")

    def _clear_all(self):
        for var in self._vars.values():
            var.set(False)

    def _save(self):
        with get_connection(DB_PATH) as conn:
            set_excluded_ids(conn, self._selected_ids())
        self._close()
        self._on_saved()

    def _close(self):
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()
