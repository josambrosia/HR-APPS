"""Pre-print options dialog for the Heatmap report.

Lets the user pick which table(s) to print (Full / Matrix / Lampiran) and
whether to include or exclude Outlier employees, then invokes a callback with
(scope, outlier) so the caller can open the print URL.
"""
import customtkinter as ctk

from src.ui.theme import (
    COLOR_BG, COLOR_SURFACE, COLOR_BORDER,
    COLOR_TEXT, COLOR_ACCENT, COLOR_ACCENT_HOVER,
    FONT_HEADING, FONT_BODY, FONT_BODY_BOLD,
    SPACE_SM, SPACE_MD, SPACE_LG, RADIUS_MD,
)


class HeatmapPrintDialog(ctk.CTkToplevel):
    """on_confirm(scope, outlier) is called when the user clicks Cetak.
    scope ∈ {'full','matrix','lampiran'}; outlier ∈ {'inc','exc'}."""

    def __init__(self, parent, on_confirm):
        super().__init__(parent)
        self._on_confirm = on_confirm
        self.scope_var = ctk.StringVar(value="full")
        self.outlier_var = ctk.StringVar(value="inc")
        self.title("Cetak Heatmap")
        self.configure(fg_color=COLOR_BG)
        try:
            self.geometry("380x320")
            self.resizable(False, False)
        except Exception:
            pass

        ctk.CTkLabel(self, text="Cetak Heatmap", font=FONT_HEADING,
                     text_color=COLOR_TEXT).pack(anchor="w", padx=SPACE_LG,
                                                 pady=(SPACE_LG, SPACE_MD))

        ctk.CTkLabel(self, text="Tabel yang dicetak:", font=FONT_BODY_BOLD,
                     text_color=COLOR_TEXT).pack(anchor="w", padx=SPACE_LG)
        for val, lab in (("full", "Full (matrix + lampiran)"),
                         ("matrix", "Matrix saja"),
                         ("lampiran", "Lampiran saja")):
            ctk.CTkRadioButton(self, text=lab, variable=self.scope_var, value=val,
                               font=FONT_BODY, text_color=COLOR_TEXT).pack(
                anchor="w", padx=SPACE_LG + 8, pady=2)

        ctk.CTkLabel(self, text="Karyawan outlier:", font=FONT_BODY_BOLD,
                     text_color=COLOR_TEXT).pack(anchor="w", padx=SPACE_LG,
                                                 pady=(SPACE_MD, 0))
        for val, lab in (("inc", "Sertakan"), ("exc", "Kecualikan")):
            ctk.CTkRadioButton(self, text=lab, variable=self.outlier_var, value=val,
                               font=FONT_BODY, text_color=COLOR_TEXT).pack(
                anchor="w", padx=SPACE_LG + 8, pady=2)

        ctk.CTkButton(self, text="Cetak", command=self._confirm,
                      fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
                      text_color=COLOR_BG, font=FONT_BODY_BOLD,
                      corner_radius=RADIUS_MD).pack(anchor="w", padx=SPACE_LG,
                                                    pady=SPACE_LG)

        self.bind("<Escape>", lambda e: self.destroy())
        try:
            self.transient(parent)
            self.grab_set()
        except Exception:
            pass

    def _confirm(self):
        scope, outlier = self.scope_var.get(), self.outlier_var.get()
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()
        self._on_confirm(scope, outlier)
