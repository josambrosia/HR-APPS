import customtkinter as ctk
from tkinter import messagebox

from src.config import DB_PATH
from src.db.connection import get_connection
from src.db.settings import get_setting, set_setting
from src.db.employees import list_employees
from src.ui.theme import FONT_FAMILY, COLOR_PANEL


class SettingsScreen(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self._build()

    def _build(self):
        ctk.CTkLabel(self, text="Settings",
                     font=(FONT_FAMILY, 24, "bold")).pack(anchor="w", pady=(0, 12))

        self.tabs = ctk.CTkTabview(self)
        self.tabs.pack(fill="both", expand=True)
        self.tabs.add("General")
        self.tabs.add("Pegawai")

        self._build_general(self.tabs.tab("General"))
        self._build_pegawai(self.tabs.tab("Pegawai"))

    def _build_general(self, parent):
        with get_connection(DB_PATH) as conn:
            current_month = get_setting(conn, "current_month", default="")
            sched_start = get_setting(conn, "schedule_start", default="08.00")
            sched_end = get_setting(conn, "schedule_end", default="16.00")
            threshold = get_setting(conn, "coaching_threshold_min", default="75")

        row = ctk.CTkFrame(parent, fg_color=COLOR_PANEL, corner_radius=6)
        row.pack(fill="x", pady=8)
        ctk.CTkLabel(row, text="Bulan Aktif (YYYY-MM):",
                     font=(FONT_FAMILY, 12)).pack(side="left", padx=12, pady=10)
        self.month_var = ctk.StringVar(value=current_month)
        ctk.CTkEntry(row, textvariable=self.month_var, width=120).pack(side="left")

        row2 = ctk.CTkFrame(parent, fg_color=COLOR_PANEL, corner_radius=6)
        row2.pack(fill="x", pady=8)
        ctk.CTkLabel(row2, text="Coaching Threshold (mnt/minggu):",
                     font=(FONT_FAMILY, 12)).pack(side="left", padx=12, pady=10)
        self.thr_var = ctk.StringVar(value=threshold)
        ctk.CTkEntry(row2, textvariable=self.thr_var, width=80).pack(side="left")

        row3 = ctk.CTkFrame(parent, fg_color=COLOR_PANEL, corner_radius=6)
        row3.pack(fill="x", pady=8)
        ctk.CTkLabel(row3, text=f"Jadwal Kerja: {sched_start} - {sched_end}",
                     font=(FONT_FAMILY, 12)).pack(side="left", padx=12, pady=10)

        ctk.CTkButton(parent, text="Simpan Pengaturan",
                      command=self._save).pack(anchor="w", pady=12)

    def _build_pegawai(self, parent):
        ctk.CTkLabel(parent, text="Pegawai auto-populated dari import. Toggle Active untuk hide dari list.",
                     font=(FONT_FAMILY, 11), text_color="#94a3b8"
                     ).pack(anchor="w", pady=(8, 4))
        self.peg_list = ctk.CTkScrollableFrame(parent, fg_color=COLOR_PANEL,
                                                corner_radius=6)
        self.peg_list.pack(fill="both", expand=True, pady=8)
        self._reload_pegawai()

    def _reload_pegawai(self):
        for w in self.peg_list.winfo_children():
            w.destroy()
        with get_connection(DB_PATH) as conn:
            rows = list_employees(conn, include_inactive=True)
        for r in rows:
            row = ctk.CTkFrame(self.peg_list, fg_color="transparent")
            row.pack(fill="x", padx=8, pady=2)
            ctk.CTkLabel(row, text=f"{r['no_staff']} · {r['nama']} · {r['dept'] or '-'}",
                         font=(FONT_FAMILY, 12), width=380, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text="Active" if r["active"] else "Inactive",
                         text_color="#4ade80" if r["active"] else "#94a3b8",
                         width=80).pack(side="left")
            ctk.CTkButton(
                row, text="Toggle",
                command=lambda eid=r["id"]: self._toggle_active(eid),
                width=80, height=24,
            ).pack(side="right")

    def _toggle_active(self, employee_id: int):
        with get_connection(DB_PATH) as conn:
            conn.execute(
                "UPDATE employees SET active = 1 - active WHERE id = ?",
                (employee_id,),
            )
        self._reload_pegawai()

    def _save(self):
        with get_connection(DB_PATH) as conn:
            set_setting(conn, "current_month", self.month_var.get().strip())
            set_setting(conn, "coaching_threshold_min", self.thr_var.get().strip())
        messagebox.showinfo("Tersimpan", "Pengaturan disimpan.")

