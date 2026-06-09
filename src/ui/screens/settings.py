from tkinter import ttk
import customtkinter as ctk
from tkinter import messagebox

from src.config import DB_PATH
from src.db.connection import get_connection
from src.db.settings import get_setting, set_setting
from src.db.employees import list_employees
from src.ui.theme import (
    FONT_FAMILY,
    COLOR_BG, COLOR_SURFACE, COLOR_SURFACE_HIGH,
    COLOR_BORDER,
    COLOR_ACCENT, COLOR_ACCENT_HOVER,
    COLOR_SECONDARY, COLOR_SECONDARY_HOVER,
    COLOR_INFO, COLOR_SUCCESS,
    COLOR_TEXT, COLOR_TEXT_DIM, COLOR_TEXT_MUTED,
    FONT_DISPLAY, FONT_HEADING,
    FONT_BODY, FONT_BODY_BOLD, FONT_SMALL,
    SPACE_XS, SPACE_SM, SPACE_MD,
    RADIUS_MD,
)


class SettingsScreen(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self._setup_treeview_style()
        self._build()

    def _setup_treeview_style(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure(
            "Pegawai.Treeview",
            background=COLOR_SURFACE, fieldbackground=COLOR_SURFACE,
            foreground=COLOR_TEXT, rowheight=24, borderwidth=0,
            font=FONT_SMALL,
        )
        style.configure(
            "Pegawai.Treeview.Heading",
            background=COLOR_SURFACE_HIGH, foreground=COLOR_TEXT_MUTED,
            relief="flat", font=(FONT_FAMILY, 9, "bold"),
        )
        style.map(
            "Pegawai.Treeview",
            background=[("selected", COLOR_SURFACE_HIGH)],
            foreground=[("selected", COLOR_TEXT)],
        )

    def _build(self):
        ctk.CTkLabel(
            self, text="Settings",
            font=FONT_DISPLAY, text_color=COLOR_TEXT,
        ).pack(anchor="w", pady=(0, SPACE_MD))

        # CTkTabview uses segmented_button_* params under the hood.
        # Selected tab → violet (COLOR_SECONDARY) to differentiate from
        # the magenta CTA reserved for primary actions like Save.
        self.tabs = ctk.CTkTabview(
            self,
            fg_color=COLOR_SURFACE,
            segmented_button_fg_color=COLOR_SURFACE,
            segmented_button_selected_color=COLOR_SECONDARY,
            segmented_button_selected_hover_color=COLOR_SECONDARY_HOVER,
            segmented_button_unselected_color=COLOR_SURFACE,
            segmented_button_unselected_hover_color=COLOR_SURFACE_HIGH,
            text_color=COLOR_TEXT,
            text_color_disabled=COLOR_TEXT_MUTED,
            corner_radius=RADIUS_MD,
        )
        self.tabs.pack(fill="both", expand=True)
        self.tabs.add("General")
        self.tabs.add("Pegawai")
        self.tabs.add("Profil")

        self._build_general(self.tabs.tab("General"))
        self._build_pegawai(self.tabs.tab("Pegawai"))
        self._build_profil(self.tabs.tab("Profil"))

    def _build_general(self, parent):
        with get_connection(DB_PATH) as conn:
            current_month = get_setting(conn, "current_month", default="")
            sched_start = get_setting(conn, "schedule_start", default="08.00")
            sched_end = get_setting(conn, "schedule_end", default="16.00")
            threshold = get_setting(conn, "coaching_threshold_per_day", default="15")
            lupa_penalty = get_setting(conn, "lupa_absen_datang_penalty_min",
                                       default="15")
            severe = get_setting(conn, "severe_lateness_threshold_min",
                                 default="60")
            tol = get_setting(conn, "late_tolerance_min", default="12")

        row = ctk.CTkFrame(
            parent, fg_color=COLOR_SURFACE,
            border_width=1, border_color=COLOR_BORDER,
            corner_radius=RADIUS_MD,
        )
        row.pack(fill="x", pady=SPACE_SM)
        ctk.CTkLabel(
            row, text="Bulan Aktif (YYYY-MM):",
            font=FONT_BODY, text_color=COLOR_TEXT,
        ).pack(side="left", padx=SPACE_MD, pady=SPACE_SM + 2)
        self.month_var = ctk.StringVar(value=current_month)
        ctk.CTkEntry(
            row, textvariable=self.month_var, width=120,
            fg_color=COLOR_SURFACE_HIGH,
            border_width=1, border_color=COLOR_BORDER,
            text_color=COLOR_TEXT,
            font=FONT_BODY,
            placeholder_text_color=COLOR_TEXT_MUTED,
        ).pack(side="left")

        row2 = ctk.CTkFrame(
            parent, fg_color=COLOR_SURFACE,
            border_width=1, border_color=COLOR_BORDER,
            corner_radius=RADIUS_MD,
        )
        row2.pack(fill="x", pady=SPACE_SM)
        ctk.CTkLabel(
            row2, text="Coaching Threshold (mnt/hari):",
            font=FONT_BODY, text_color=COLOR_TEXT,
        ).pack(side="left", padx=SPACE_MD, pady=SPACE_SM + 2)
        self.thr_var = ctk.StringVar(value=threshold)
        ctk.CTkEntry(
            row2, textvariable=self.thr_var, width=80,
            fg_color=COLOR_SURFACE_HIGH,
            border_width=1, border_color=COLOR_BORDER,
            text_color=COLOR_TEXT,
            font=FONT_BODY,
            placeholder_text_color=COLOR_TEXT_MUTED,
        ).pack(side="left")

        row3 = ctk.CTkFrame(
            parent, fg_color=COLOR_SURFACE,
            border_width=1, border_color=COLOR_BORDER,
            corner_radius=RADIUS_MD,
        )
        row3.pack(fill="x", pady=SPACE_SM)
        ctk.CTkLabel(
            row3, text=f"Jadwal Kerja: {sched_start} - {sched_end}",
            font=FONT_BODY, text_color=COLOR_TEXT,
        ).pack(side="left", padx=SPACE_MD, pady=SPACE_SM + 2)

        row4 = ctk.CTkFrame(
            parent, fg_color=COLOR_SURFACE,
            border_width=1, border_color=COLOR_BORDER,
            corner_radius=RADIUS_MD,
        )
        row4.pack(fill="x", pady=SPACE_SM)
        ctk.CTkLabel(
            row4, text="Penalti Lupa Absen Datang (menit):",
            font=FONT_BODY, text_color=COLOR_TEXT,
        ).pack(side="left", padx=SPACE_MD, pady=SPACE_SM + 2)
        self.lupa_penalty_var = ctk.StringVar(value=lupa_penalty)
        ctk.CTkEntry(
            row4, textvariable=self.lupa_penalty_var, width=80,
            fg_color=COLOR_SURFACE_HIGH,
            border_width=1, border_color=COLOR_BORDER,
            text_color=COLOR_TEXT,
            font=FONT_BODY,
            placeholder_text_color=COLOR_TEXT_MUTED,
        ).pack(side="left")

        row5 = ctk.CTkFrame(
            parent, fg_color=COLOR_SURFACE,
            border_width=1, border_color=COLOR_BORDER,
            corner_radius=RADIUS_MD,
        )
        row5.pack(fill="x", pady=SPACE_SM)
        ctk.CTkLabel(
            row5, text="Severe Lateness Threshold (menit):",
            font=FONT_BODY, text_color=COLOR_TEXT,
        ).pack(side="left", padx=SPACE_MD, pady=SPACE_SM + 2)
        self.severe_var = ctk.StringVar(value=severe)
        ctk.CTkEntry(
            row5, textvariable=self.severe_var, width=80,
            fg_color=COLOR_SURFACE_HIGH,
            border_width=1, border_color=COLOR_BORDER,
            text_color=COLOR_TEXT,
            font=FONT_BODY,
            placeholder_text_color=COLOR_TEXT_MUTED,
        ).pack(side="left")

        row6 = ctk.CTkFrame(
            parent, fg_color=COLOR_SURFACE,
            border_width=1, border_color=COLOR_BORDER,
            corner_radius=RADIUS_MD,
        )
        row6.pack(fill="x", pady=SPACE_SM)
        ctk.CTkLabel(
            row6, text="Toleransi Telat (menit):",
            font=FONT_BODY, text_color=COLOR_TEXT,
        ).pack(side="left", padx=SPACE_MD, pady=SPACE_SM + 2)
        self.tol_var = ctk.StringVar(value=tol)
        ctk.CTkEntry(
            row6, textvariable=self.tol_var, width=80,
            fg_color=COLOR_SURFACE_HIGH,
            border_width=1, border_color=COLOR_BORDER,
            text_color=COLOR_TEXT,
            font=FONT_BODY,
            placeholder_text_color=COLOR_TEXT_MUTED,
        ).pack(side="left")

        # Save = magenta primary CTA (JTS brand action color).
        ctk.CTkButton(
            parent, text="Simpan Pengaturan",
            command=self._save,
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
            text_color=COLOR_BG,
            font=FONT_BODY_BOLD,
            corner_radius=RADIUS_MD,
        ).pack(anchor="w", pady=SPACE_MD)

    def _build_profil(self, parent):
        with get_connection(DB_PATH) as conn:
            hr_name = get_setting(conn, "hr_officer_name", default="")

        ctk.CTkLabel(
            parent,
            text="Nama ini muncul di hasil cetak Dashboard sebagai "
                 "HR Officer in Charge.",
            font=FONT_SMALL, text_color=COLOR_TEXT_DIM,
        ).pack(anchor="w", pady=(SPACE_SM, SPACE_XS))

        row = ctk.CTkFrame(
            parent, fg_color=COLOR_SURFACE,
            border_width=1, border_color=COLOR_BORDER,
            corner_radius=RADIUS_MD,
        )
        row.pack(fill="x", pady=SPACE_SM)
        ctk.CTkLabel(
            row, text="Nama:",
            font=FONT_BODY, text_color=COLOR_TEXT,
        ).pack(side="left", padx=SPACE_MD, pady=SPACE_SM + 2)
        self.hr_name_var = ctk.StringVar(value=hr_name)
        ctk.CTkEntry(
            row, textvariable=self.hr_name_var, width=260,
            fg_color=COLOR_SURFACE_HIGH,
            border_width=1, border_color=COLOR_BORDER,
            text_color=COLOR_TEXT,
            font=FONT_BODY,
            placeholder_text_color=COLOR_TEXT_MUTED,
        ).pack(side="left")

        ctk.CTkButton(
            parent, text="Simpan Profil",
            command=self._save_profil,
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
            text_color=COLOR_BG,
            font=FONT_BODY_BOLD,
            corner_radius=RADIUS_MD,
        ).pack(anchor="w", pady=SPACE_MD)

    def _build_pegawai(self, parent):
        ctk.CTkLabel(
            parent,
            text="Pegawai auto-populated dari import. Toggle Active untuk hide dari list.",
            font=FONT_SMALL, text_color=COLOR_TEXT_DIM,
        ).pack(anchor="w", pady=(SPACE_SM, SPACE_XS))

        # Treeview-based list for consistency with Coaching / Issues / Dashboard.
        wrap = ctk.CTkFrame(
            parent, fg_color=COLOR_SURFACE,
            border_width=1, border_color=COLOR_BORDER,
            corner_radius=RADIUS_MD,
        )
        wrap.pack(fill="both", expand=True, pady=SPACE_SM)

        cols = ["no_staff", "nama", "dept", "status"]
        widths = {"no_staff": 100, "nama": 220, "dept": 140, "status": 90}
        labels = {"no_staff": "No Staff", "nama": "Nama",
                  "dept": "Dept", "status": "Status"}

        self.tree = ttk.Treeview(
            wrap, columns=cols, show="headings",
            style="Pegawai.Treeview", selectmode="browse", height=14,
        )
        for c in cols:
            self.tree.heading(c, text=labels[c])
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.tag_configure("active", foreground=COLOR_SUCCESS)
        self.tree.tag_configure("inactive", foreground=COLOR_TEXT_MUTED)
        self.tree.pack(fill="both", expand=True, padx=SPACE_SM, pady=SPACE_SM)

        # Toggle button row below treeview.
        actions = ctk.CTkFrame(parent, fg_color="transparent")
        actions.pack(fill="x", pady=(SPACE_SM, 0))
        ctk.CTkButton(
            actions, text="Toggle Active",
            command=self._toggle_selected,
            fg_color="transparent",
            border_width=1, border_color=COLOR_INFO,
            text_color=COLOR_INFO,
            hover_color=COLOR_SURFACE_HIGH,
            font=FONT_BODY_BOLD,
            corner_radius=RADIUS_MD,
            width=140,
        ).pack(side="right")

        self._reload_pegawai()

    def _reload_pegawai(self):
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        with get_connection(DB_PATH) as conn:
            rows = list_employees(conn, include_inactive=True)
        for r in rows:
            status = "Active" if r["active"] else "Inactive"
            tag = "active" if r["active"] else "inactive"
            self.tree.insert(
                "", "end", iid=str(r["id"]),
                values=(r["no_staff"], r["nama"], r["dept"] or "-", status),
                tags=(tag,),
            )

    def _toggle_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        try:
            employee_id = int(sel[0])
        except ValueError:
            return
        self._toggle_active(employee_id)

    def _toggle_active(self, employee_id: int):
        with get_connection(DB_PATH) as conn:
            conn.execute(
                "UPDATE employees SET active = 1 - active WHERE id = ?",
                (employee_id,),
            )
        self._reload_pegawai()

    def _save(self):
        # Validate Lupa Absen Datang penalty: integer in [0, 999]
        raw = self.lupa_penalty_var.get().strip()
        try:
            penalty = int(raw)
        except ValueError:
            messagebox.showwarning(
                "Penalti tidak valid",
                f"'{raw}' bukan angka. Penalti harus berupa bilangan "
                f"bulat antara 0 dan 999.")
            return
        if penalty < 0 or penalty > 999:
            messagebox.showwarning(
                "Penalti di luar rentang",
                f"{penalty} di luar rentang yang diizinkan. "
                f"Penalti harus antara 0 dan 999 menit.")
            return
        # Validate Severe Lateness threshold: integer in [1, 999]
        raw_sev = self.severe_var.get().strip()
        try:
            severe = int(raw_sev)
        except ValueError:
            messagebox.showwarning(
                "Threshold tidak valid",
                f"'{raw_sev}' bukan angka. Threshold harus bilangan bulat "
                f"antara 1 dan 999.")
            return
        if severe < 1 or severe > 999:
            messagebox.showwarning(
                "Threshold di luar rentang",
                f"{severe} di luar rentang. Threshold harus antara 1 dan 999 menit.")
            return
        # Validate Toleransi Telat: integer in [0, 999]
        raw_tol = self.tol_var.get().strip()
        try:
            tol = int(raw_tol)
        except ValueError:
            messagebox.showwarning(
                "Toleransi tidak valid",
                f"'{raw_tol}' bukan angka. Toleransi harus bilangan bulat "
                f"antara 0 dan 999.")
            return
        if tol < 0 or tol > 999:
            messagebox.showwarning(
                "Toleransi di luar rentang",
                f"{tol} di luar rentang. Toleransi harus antara 0 dan 999 menit.")
            return
        with get_connection(DB_PATH) as conn:
            set_setting(conn, "current_month", self.month_var.get().strip())
            set_setting(conn, "coaching_threshold_per_day", self.thr_var.get().strip())
            set_setting(conn, "lupa_absen_datang_penalty_min", str(penalty))
            set_setting(conn, "severe_lateness_threshold_min", str(severe))
            set_setting(conn, "late_tolerance_min", str(tol))
        messagebox.showinfo("Tersimpan", "Pengaturan disimpan.")

    def _save_profil(self):
        with get_connection(DB_PATH) as conn:
            set_setting(conn, "hr_officer_name", self.hr_name_var.get().strip())
        messagebox.showinfo("Tersimpan", "Profil disimpan.")
