from pathlib import Path
from tkinter import filedialog, messagebox
import customtkinter as ctk

from src.config import DB_PATH
from src.db.connection import get_connection
from src.db.employees import upsert_employee, get_employee_by_no_staff
from src.db.attendance import upsert_attendance
from src.parsers.fingerprint import parse_fingerprint_file
from src.core.issue_detector import is_issue
from src.ui.theme import FONT_FAMILY, COLOR_OK


class ImportScreen(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self._build()

    def _build(self):
        ctk.CTkLabel(self, text="Import Fingerprint",
                     font=(FONT_FAMILY, 24, "bold")).pack(anchor="w", pady=(0, 20))

        ctk.CTkButton(self, text="📁 Pilih file .xls / .xlsx",
                      command=self._on_pick_file, height=40).pack(pady=10)

        self.preview = ctk.CTkTextbox(self, width=700, height=300,
                                      font=("Consolas", 12))
        self.preview.pack(padx=20, pady=10, fill="both", expand=True)
        self.preview.insert("1.0", "(belum ada file dipilih)")
        self.preview.configure(state="disabled")

        self.import_btn = ctk.CTkButton(self, text="Konfirmasi Impor",
                                        command=self._on_confirm,
                                        state="disabled", height=40,
                                        fg_color=COLOR_OK, text_color="#0a0a0a")
        self.import_btn.pack(pady=10)

        self._pending_path: Path | None = None
        self._pending_rows: list = []

    def _on_pick_file(self):
        path = filedialog.askopenfilename(
            title="Pilih file fingerprint",
            filetypes=[("Excel", "*.xls *.xlsx"), ("All files", "*.*")],
        )
        if not path:
            return
        self._pending_path = Path(path)
        try:
            self._pending_rows = parse_fingerprint_file(self._pending_path)
        except Exception as e:
            messagebox.showerror("Error parsing", str(e))
            return

        issue_count = sum(1 for r in self._pending_rows if is_issue(r))
        unique_emps = {r.no_staff for r in self._pending_rows}
        dates = sorted({r.tanggal for r in self._pending_rows})
        date_range = f"{dates[0]} → {dates[-1]}" if dates else "(empty)"

        text = (
            f"File: {self._pending_path.name}\n"
            f"Pegawai: {len(unique_emps)}\n"
            f"Range tanggal: {date_range}\n"
            f"Total baris: {len(self._pending_rows)}\n"
            f"Issue terdeteksi (Masuk/Keluar kosong di Hari Kerja): {issue_count}\n"
        )
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.insert("1.0", text)
        self.preview.configure(state="disabled")
        self.import_btn.configure(state="normal")

    def _on_confirm(self):
        with get_connection(DB_PATH) as conn:
            for r in self._pending_rows:
                emp_id = upsert_employee(
                    conn, no_staff=r.no_staff, nama=r.nama, dept=r.dept
                )
                upsert_attendance(
                    conn, employee_id=emp_id, tanggal=r.tanggal,
                    hari=r.hari, tipe=r.tipe, jadwal=r.jadwal,
                    masuk=r.masuk, keluar=r.keluar,
                    kerja_jam=r.kerja_jam, lembur_jam=r.lembur_jam,
                    terlambat_menit=r.terlambat_menit,
                    has_issue=1 if is_issue(r) else 0,
                    imported_from=r.source_file,
                )
        messagebox.showinfo("Sukses", f"Impor {len(self._pending_rows)} baris selesai.")
        self.import_btn.configure(state="disabled")
        self._pending_rows = []
        self._pending_path = None
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.insert("1.0", "(impor selesai. Pilih file lain bila perlu.)")
        self.preview.configure(state="disabled")
