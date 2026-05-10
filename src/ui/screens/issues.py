from typing import Optional
import customtkinter as ctk
from tkinter import messagebox

from src.config import DB_PATH
from src.db.connection import get_connection
from src.db.attendance import set_reason, list_open_issues
from src.core.reason_mapper import REASON_LABELS, REASON_NEEDS_DETAIL
from src.ui.components.data_table import DataTable
from src.ui.theme import FONT_FAMILY, COLOR_OK, COLOR_PANEL


class IssuesScreen(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self.grid_columnconfigure(0, weight=2)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.selected: Optional[dict] = None
        self._build()
        self._reload()

    def _build(self):
        # Left: table
        left = ctk.CTkFrame(self, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        ctk.CTkLabel(left, text="Issues (open)", font=(FONT_FAMILY, 20, "bold")
                     ).pack(anchor="w", pady=(0, 10))
        self.table = DataTable(
            left,
            columns=["Tanggal", "Hari", "Nama", "Dept", "Masuk", "Keluar"],
            col_widths=[100, 80, 130, 100, 70, 70],
            on_row_click=self._on_row_click,
        )
        self.table.pack(fill="both", expand=True)

        # Right: reason panel
        right = ctk.CTkFrame(self, fg_color=COLOR_PANEL, corner_radius=8)
        right.grid(row=0, column=1, sticky="nsew")
        self.right = right
        self._build_panel_empty()

    def _build_panel_empty(self):
        for w in self.right.winfo_children():
            w.destroy()
        ctk.CTkLabel(self.right, text="Pilih issue di kiri untuk input alasan",
                     font=(FONT_FAMILY, 12), text_color="#94a3b8"
                     ).pack(pady=80, padx=16)

    def _build_panel_for(self, issue: dict):
        for w in self.right.winfo_children():
            w.destroy()
        info = (
            f"{issue['nama']} ({issue['dept']})\n"
            f"{issue['hari']}, {issue['tanggal']}\n"
            f"Masuk: {issue['masuk'] or '—'}   Keluar: {issue['keluar'] or '—'}"
        )
        ctk.CTkLabel(self.right, text=info, justify="left",
                     font=(FONT_FAMILY, 12)).pack(anchor="w", padx=16, pady=(16, 12))

        ctk.CTkLabel(self.right, text="Kategori alasan:",
                     font=(FONT_FAMILY, 11)).pack(anchor="w", padx=16)
        self.cat_var = ctk.StringVar(value="")
        self.cat_combo = ctk.CTkComboBox(
            self.right,
            values=[f"{k} — {v}" for k, v in REASON_LABELS.items()],
            variable=self.cat_var, width=300,
            command=self._on_cat_change,
        )
        self.cat_combo.pack(anchor="w", padx=16, pady=(4, 12))

        self.detail_label = ctk.CTkLabel(self.right, text="Detail:",
                                          font=(FONT_FAMILY, 11))
        self.detail_entry = ctk.CTkEntry(self.right, width=300)
        # Show only when category needs detail
        self.detail_label.pack_forget()
        self.detail_entry.pack_forget()

        ctk.CTkButton(self.right, text="Simpan",
                      command=self._on_save, fg_color=COLOR_OK,
                      text_color="#0a0a0a", width=300
                      ).pack(anchor="w", padx=16, pady=12)

    def _on_cat_change(self, _):
        cat = self.cat_var.get().split(" — ")[0]
        if cat in REASON_NEEDS_DETAIL:
            self.detail_label.pack(anchor="w", padx=16)
            self.detail_entry.pack(anchor="w", padx=16, pady=(4, 12))
        else:
            self.detail_label.pack_forget()
            self.detail_entry.pack_forget()

    def _on_row_click(self, issue: dict):
        self.selected = issue
        self._build_panel_for(issue)

    def _on_save(self):
        if not self.selected:
            return
        cat = self.cat_var.get().split(" — ")[0] if " — " in self.cat_var.get() else ""
        if cat not in REASON_LABELS:
            messagebox.showwarning("Pilih kategori", "Belum memilih kategori alasan.")
            return
        detail = self.detail_entry.get().strip() if cat in REASON_NEEDS_DETAIL else None
        with get_connection(DB_PATH) as conn:
            set_reason(conn, attendance_id=self.selected["id"],
                       category=cat, detail=detail or None)
        self._reload()
        self._build_panel_empty()

    def _reload(self):
        with get_connection(DB_PATH) as conn:
            rows = list_open_issues(conn)
        rows_as_dict = [dict(r) for r in rows]
        self.table.set_rows(
            rows_as_dict,
            values_fn=lambda r: [
                r["tanggal"], r["hari"] or "—", r["nama"],
                r["dept"] or "—", r["masuk"] or "—", r["keluar"] or "—",
            ],
        )
