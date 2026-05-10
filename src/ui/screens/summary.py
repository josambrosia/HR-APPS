import customtkinter as ctk
import pyperclip
from tkinter import messagebox

from src.config import DB_PATH
from src.db.connection import get_connection
from src.core.issue_summary import render_summary_for_employee
from src.ui.theme import FONT_FAMILY, COLOR_PANEL, COLOR_OK


class SummaryScreen(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(0, weight=1)
        self._build()
        self._reload()

    def _build(self):
        left = ctk.CTkFrame(self, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        ctk.CTkLabel(left, text="Pegawai (open issues)",
                     font=(FONT_FAMILY, 16, "bold")).pack(anchor="w", pady=(0, 10))
        self.list_frame = ctk.CTkScrollableFrame(left, fg_color=COLOR_PANEL,
                                                  corner_radius=6)
        self.list_frame.pack(fill="both", expand=True)

        right = ctk.CTkFrame(self, fg_color=COLOR_PANEL, corner_radius=8)
        right.grid(row=0, column=1, sticky="nsew")
        self.right = right
        ctk.CTkLabel(self.right, text="Pilih pegawai di kiri",
                     font=(FONT_FAMILY, 12), text_color="#94a3b8").pack(pady=80)

    def _reload(self):
        for w in self.list_frame.winfo_children():
            w.destroy()
        with get_connection(DB_PATH) as conn:
            rows = conn.execute(
                """
                SELECT e.id, e.nama, COUNT(*) AS open_cnt
                  FROM attendance_records ar
                  JOIN employees e ON ar.employee_id = e.id
                 WHERE ar.has_issue = 1 AND ar.reason_category IS NULL
                 GROUP BY e.id
                 ORDER BY e.nama
                """
            ).fetchall()
        if not rows:
            ctk.CTkLabel(self.list_frame, text="(tidak ada open issue)",
                         font=(FONT_FAMILY, 12), text_color="#94a3b8").pack(pady=20)
            return
        for r in rows:
            btn = ctk.CTkButton(
                self.list_frame, text=f"{r['nama']}  ({r['open_cnt']})",
                anchor="w", fg_color="transparent", hover_color="#334155",
                command=lambda emp_id=r["id"]: self._show_for(emp_id),
            )
            btn.pack(fill="x", padx=4, pady=2)

    def _show_for(self, emp_id: int):
        for w in self.right.winfo_children():
            w.destroy()
        with get_connection(DB_PATH) as conn:
            text = render_summary_for_employee(conn, emp_id)
        if not text:
            ctk.CTkLabel(self.right, text="(tidak ada open issue)",
                         font=(FONT_FAMILY, 12)).pack(pady=80)
            return
        box = ctk.CTkTextbox(self.right, font=("Consolas", 13))
        box.pack(fill="both", expand=True, padx=16, pady=16)
        box.insert("1.0", text)
        box.configure(state="disabled")
        ctk.CTkButton(self.right, text="📋 Copy ke Clipboard",
                      fg_color=COLOR_OK, text_color="#0a0a0a",
                      command=lambda t=text: self._copy(t)
                      ).pack(pady=(0, 16))

    def _copy(self, text: str):
        pyperclip.copy(text)
        messagebox.showinfo("Copied", "Teks sudah masuk clipboard.")
