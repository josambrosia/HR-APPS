"""Modal to add a new effective-dated work-schedule period (v26).

HR memilih tanggal berlaku + jam masuk/pulang. Entri lama tidak diubah;
perbaikan dilakukan dengan menambah periode baru. Tanggal minimal hari ini.
"""
from datetime import date

import customtkinter as ctk

from src.config import DB_PATH
from src.core.attendance_calc import to_minutes
from src.core.schedule import validate_period
from src.db.connection import get_connection
from src.db.schedule import add_period, list_periods
from src.ui import feedback
from src.ui.theme import (
    COLOR_BG, COLOR_SURFACE_HIGH, COLOR_BORDER, COLOR_ACCENT,
    COLOR_ACCENT_HOVER, COLOR_INFO, COLOR_TEXT, COLOR_TEXT_MUTED,
    FONT_HEADING, FONT_BODY, FONT_BODY_BOLD, FONT_SMALL, FONT_LABEL,
    SPACE_XS, SPACE_SM, SPACE_MD, SPACE_LG, RADIUS_MD,
)

DIALOG_W = 400


class ScheduleChangeDialog(ctk.CTkToplevel):
    def __init__(self, parent, on_saved):
        super().__init__(parent)
        self._on_saved = on_saved
        self.title("Tambah Perubahan Jadwal")
        self.configure(fg_color=COLOR_BG)
        self.resizable(False, False)
        self.transient(parent)

        ctk.CTkLabel(
            self, text="Perubahan Jam Kantor", font=FONT_HEADING,
            text_color=COLOR_TEXT, anchor="w",
        ).pack(fill="x", padx=SPACE_LG, pady=(SPACE_LG, 0))
        ctk.CTkLabel(
            self,
            text="Jadwal baru berlaku mulai tanggal di bawah. Jadwal lama "
                 "tetap dipakai untuk tanggal sebelumnya.",
            font=FONT_SMALL, text_color=COLOR_TEXT_MUTED, anchor="w",
            wraplength=DIALOG_W - 2 * SPACE_LG, justify="left",
        ).pack(fill="x", padx=SPACE_LG, pady=(2, SPACE_SM))

        ctk.CTkLabel(self, text="BERLAKU MULAI (YYYY-MM-DD)", font=FONT_LABEL,
                     text_color=COLOR_TEXT_MUTED, anchor="w").pack(
            fill="x", padx=SPACE_LG)
        self._tanggal = self._entry(self, date.today().isoformat())
        self._tanggal.pack(fill="x", padx=SPACE_LG)

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=SPACE_LG, pady=(SPACE_SM, 0))
        row.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkLabel(row, text="JAM MASUK (HH.MM)", font=FONT_LABEL,
                     text_color=COLOR_TEXT_MUTED, anchor="w").grid(
            row=0, column=0, sticky="w")
        ctk.CTkLabel(row, text="JAM PULANG (HH.MM)", font=FONT_LABEL,
                     text_color=COLOR_TEXT_MUTED, anchor="w").grid(
            row=0, column=1, sticky="w", padx=(SPACE_SM, 0))
        self._masuk = self._entry(row, "09.00")
        self._keluar = self._entry(row, "17.00")
        self._masuk.grid(row=1, column=0, sticky="ew", padx=(0, SPACE_SM))
        self._keluar.grid(row=1, column=1, sticky="ew")

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=SPACE_LG, pady=(SPACE_MD, SPACE_LG))
        ctk.CTkButton(
            footer, text="Simpan", command=self._save, width=110,
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
            text_color=COLOR_BG, font=FONT_BODY_BOLD, corner_radius=RADIUS_MD,
        ).pack(side="right")
        ctk.CTkButton(
            footer, text="Batal", command=self._close, width=90,
            fg_color="transparent", border_width=1, border_color=COLOR_INFO,
            text_color=COLOR_INFO, hover_color=COLOR_SURFACE_HIGH,
            font=FONT_BODY_BOLD, corner_radius=RADIUS_MD,
        ).pack(side="right", padx=(0, SPACE_SM))

        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        h = self.winfo_reqheight()
        x, y = (sw - DIALOG_W) // 2, max(0, (sh - h) // 2)
        self.geometry(f"{DIALOG_W}x{h}+{x}+{y}")
        self.after(50, lambda: (self.grab_set(), self.focus_set()))
        self.bind("<Escape>", lambda _e: self._close())
        self.bind("<Return>", lambda _e: (self._save(), "break")[1])

    def _entry(self, parent, value=""):
        e = ctk.CTkEntry(
            parent, fg_color=COLOR_SURFACE_HIGH, border_width=1,
            border_color=COLOR_BORDER, text_color=COLOR_TEXT, font=FONT_BODY)
        e.insert(0, value)
        return e

    def _regrab(self):
        try:
            self.grab_set()
        except Exception:
            pass

    def _save(self):
        tgl = self._tanggal.get().strip()
        masuk = self._masuk.get().strip()
        keluar = self._keluar.get().strip()
        err = validate_period(tgl, masuk, keluar)
        if err:
            feedback.show_warning(self, "Jadwal tidak valid", err)
            self._regrab()
            return
        if date.fromisoformat(tgl) < date.today():
            feedback.show_warning(
                self, "Tanggal tidak boleh di masa lalu",
                "Jadwal hanya bisa berlaku mulai hari ini atau setelahnya. "
                "Perubahan masa lalu hanya terjadi lewat migrasi.")
            self._regrab()
            return
        if to_minutes(masuk) is None or to_minutes(keluar) is None:
            feedback.show_warning(
                self, "Jam tidak valid",
                "Format jam harus HH.MM (mis. 09.00).")
            self._regrab()
            return
        with get_connection(DB_PATH) as conn:
            if any(p["effective_from"] == tgl for p in list_periods(conn)):
                feedback.show_warning(
                    self, "Tanggal sudah dipakai",
                    f"Sudah ada jadwal yang berlaku mulai {tgl}. "
                    "Pilih tanggal lain.")
                self._regrab()
                return
            add_period(conn, effective_from=tgl, start=masuk, end=keluar)
        self._on_saved()
        self.destroy()

    def _close(self):
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()
