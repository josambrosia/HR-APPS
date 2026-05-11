from pathlib import Path
from tkinter import filedialog, messagebox
import customtkinter as ctk

from src.config import DB_PATH
from src.db.connection import get_connection
from src.core.report_filler import fill_monthly_report
from src.ui.theme import FONT_FAMILY, COLOR_OK, COLOR_PANEL


class ExportScreen(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self._selected: Path | None = None
        self._build()

    def _build(self):
        ctk.CTkLabel(self, text="Export Laporan Bulanan",
                     font=(FONT_FAMILY, 24, "bold")).pack(anchor="w", pady=(0, 20))

        ctk.CTkButton(self, text="📁 Pilih Laporan Bulanan (.xlsx)",
                      command=self._pick).pack(pady=10)

        self.info = ctk.CTkLabel(self, text="(belum ada file dipilih)",
                                  font=(FONT_FAMILY, 12), text_color="#94a3b8")
        self.info.pack(pady=10)

        self.export_btn = ctk.CTkButton(
            self, text="💾 Export filled .xlsx",
            command=self._do_export, fg_color=COLOR_OK,
            text_color="#0a0a0a", state="disabled", height=40,
        )
        self.export_btn.pack(pady=10)

    def _pick(self):
        path = filedialog.askopenfilename(
            title="Pilih Laporan Bulanan",
            filetypes=[("Excel", "*.xlsx")],
        )
        if not path:
            return
        self._selected = Path(path)
        self.info.configure(text=f"File: {self._selected.name}")
        self.export_btn.configure(state="normal")

    def _do_export(self):
        if not self._selected:
            return
        try:
            with get_connection(DB_PATH) as conn:
                out_path, summary = fill_monthly_report(self._selected, conn)
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return
        messagebox.showinfo(
            "Sukses",
            f"File: {out_path.name}\n"
            f"Filled: {summary.filled_count} · "
            f"NA: {summary.na_count} · "
            f"Not found: {summary.not_found_count}",
        )
