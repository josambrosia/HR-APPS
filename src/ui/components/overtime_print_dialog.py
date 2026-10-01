"""Pre-print options dialog for the Lembur report (v26).

Mode "all" (semua status) atau "accepted" (hanya Diterima — untuk pembayaran).
"""
import customtkinter as ctk

from src.ui.theme import (
    COLOR_BG, COLOR_TEXT, COLOR_ACCENT, COLOR_ACCENT_HOVER,
    FONT_HEADING, FONT_BODY, FONT_BODY_BOLD,
    SPACE_MD, SPACE_LG, RADIUS_MD,
)


class OvertimePrintDialog(ctk.CTkToplevel):
    """on_confirm(mode) dipanggil saat user menekan Cetak; mode ∈ {'all','accepted'}."""

    def __init__(self, parent, on_confirm):
        super().__init__(parent)
        self._on_confirm = on_confirm
        self.mode_var = ctk.StringVar(value="all")
        self.title("Cetak Laporan Lembur")
        self.configure(fg_color=COLOR_BG)
        try:
            self.geometry("380x250")
            self.resizable(False, False)
        except Exception:
            pass

        ctk.CTkLabel(self, text="Cetak Laporan Lembur", font=FONT_HEADING,
                     text_color=COLOR_TEXT).pack(anchor="w", padx=SPACE_LG,
                                                 pady=(SPACE_LG, SPACE_MD))
        ctk.CTkLabel(self, text="Baris yang dicetak:", font=FONT_BODY_BOLD,
                     text_color=COLOR_TEXT).pack(anchor="w", padx=SPACE_LG)
        for val, lab in (
                ("all", "Semua status (rekap lengkap)"),
                ("accepted", "Hanya Diterima (untuk pembayaran)")):
            ctk.CTkRadioButton(self, text=lab, variable=self.mode_var, value=val,
                               font=FONT_BODY, text_color=COLOR_TEXT).pack(
                anchor="w", padx=SPACE_LG + 8, pady=2)

        ctk.CTkButton(self, text="Cetak", command=self._confirm,
                      fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
                      text_color=COLOR_BG, font=FONT_BODY_BOLD,
                      corner_radius=RADIUS_MD).pack(anchor="w", padx=SPACE_LG,
                                                    pady=SPACE_LG)
        self.bind("<Escape>", lambda _e: self.destroy())
        try:
            self.transient(parent)
            self.grab_set()
        except Exception:
            pass

    def _confirm(self):
        mode = self.mode_var.get()
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()
        self._on_confirm(mode)
