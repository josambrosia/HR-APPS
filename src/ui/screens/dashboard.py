import webbrowser
import tempfile
from datetime import date, timedelta
from pathlib import Path

import customtkinter as ctk
from tkinter import messagebox

from src.config import DB_PATH
from src.db.connection import get_connection
from src.db.settings import get_setting
from src.core.insights import (
    terlambat_ranking, top_n_terlambat, coaching_flag, karyawan_teladan
)
from src.core.week_utils import weeks_in_month, full_month_range
from src.reports.html_renderer import render_dashboard_html
from src.ui.components.kpi_card import KPICard
from src.ui.theme import FONT_FAMILY, COLOR_OK, COLOR_WARN, COLOR_PANEL


class DashboardScreen(ctk.CTkFrame):
    """Dashboard = analytics view (KPIs, top 5 terlambat, coaching flag, ranking).

    Period selector lets user switch between Bulanan (full month) and Mingguan
    (specific week within the current month).
    """

    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)

        # Cache current_month value at construction
        with get_connection(DB_PATH) as conn:
            self._current_month = get_setting(conn, "current_month") or ""

        self._build_header()
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.grid(row=1, column=0, sticky="nsew")
        self.grid_rowconfigure(1, weight=1)

        self.period_var = ctk.StringVar(value="Bulanan")
        self.week_var = ctk.StringVar(value="Minggu 1")
        self._reload()

    # ------------------------------------------------------------------ Header

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 16))

        ctk.CTkLabel(
            header, text="Dashboard", font=(FONT_FAMILY, 24, "bold")
        ).pack(side="left")

        # Right-side controls (right-to-left order due to pack(side="right"))
        ctk.CTkButton(
            header, text="📄 Cetak / Export PDF",
            fg_color=COLOR_OK, text_color="#0a0a0a",
            command=self._on_print,
        ).pack(side="right", padx=(8, 0))

        # Period selector
        self.period_var = ctk.StringVar(value="Bulanan")
        ctk.CTkSegmentedButton(
            header, values=["Mingguan", "Bulanan"],
            variable=self.period_var, command=lambda _: self._on_period_change(),
        ).pack(side="right", padx=8)

        # Week picker (only meaningful when period=Mingguan)
        self.week_var = ctk.StringVar(value="")
        self.week_picker = ctk.CTkOptionMenu(
            header, variable=self.week_var,
            values=self._week_labels(),
            command=lambda _: self._reload(),
            width=160,
        )
        self.week_picker.pack(side="right", padx=8)
        # Default-pick most recent week with data
        self._default_pick_week()

    def _week_labels(self):
        """Return list of "Minggu N (DD-DD MMM)" labels for current_month."""
        if not self._current_month:
            return ["(set current_month)"]
        weeks = weeks_in_month(self._current_month)
        out = []
        for num, start, end in weeks:
            s_day = start.split("-")[2]
            e_day = end.split("-")[2]
            out.append(f"Minggu {num} ({s_day}-{e_day})")
        return out

    def _default_pick_week(self):
        """Pick the week containing the most recent imported_at date."""
        if not self._current_month:
            return
        weeks = weeks_in_month(self._current_month)
        if not weeks:
            return
        with get_connection(DB_PATH) as conn:
            row = conn.execute(
                "SELECT MAX(tanggal) AS d FROM attendance_records"
            ).fetchone()
        last_date = row["d"] if row and row["d"] else None
        chosen = weeks[0]
        if last_date:
            for num, start, end in weeks:
                if start <= last_date <= end:
                    chosen = (num, start, end)
                    break
        self.week_var.set(self._week_labels()[chosen[0] - 1])

    def _on_period_change(self):
        # Enable/disable week picker based on period
        period = self.period_var.get()
        if period == "Mingguan":
            self.week_picker.configure(state="normal")
        else:
            self.week_picker.configure(state="disabled")
        self._reload()

    # ------------------------------------------------------------------ Range

    def _period_range(self):
        """Return (start_iso, end_iso, label) based on period + week selection."""
        period = self.period_var.get()
        if period == "Mingguan" and self._current_month:
            weeks = weeks_in_month(self._current_month)
            label = self.week_var.get()
            # Extract week number from label like "Minggu 2 (08-14)"
            try:
                week_num = int(label.split()[1])
            except (IndexError, ValueError):
                week_num = 1
            for num, start, end in weeks:
                if num == week_num:
                    return start, end, f"Minggu {num} ({start} → {end})"
            # fallback
            num, start, end = weeks[0]
            return start, end, f"Minggu {num} ({start} → {end})"

        # Bulanan
        if self._current_month:
            start, end = full_month_range(self._current_month)
            return start, end, f"Bulanan ({self._current_month})"

        # Fallback: last 30 days
        today = date.today()
        return (today - timedelta(days=30)).isoformat(), today.isoformat(), "Last 30 days"

    # ------------------------------------------------------------------ Body

    def _reload(self):
        for w in self.body.winfo_children():
            w.destroy()

        start, end, label = self._period_range()
        with get_connection(DB_PATH) as conn:
            ranking = terlambat_ranking(conn, start, end)
            top5 = top_n_terlambat(conn, start, end, 5)
            coaching = coaching_flag(conn, start, end)
            teladan = karyawan_teladan(conn, start, end)

        # KPI row (4 cards)
        kpi_frame = ctk.CTkFrame(self.body, fg_color="transparent")
        kpi_frame.pack(fill="x", pady=(0, 12))
        for i in range(4):
            kpi_frame.grid_columnconfigure(i, weight=1)

        total_late = sum(r["total_terlambat"] for r in ranking)
        teladan_name = teladan["nama"] if teladan else "-"

        KPICard(kpi_frame, "Periode", label).grid(row=0, column=0, padx=4, sticky="ew")
        KPICard(kpi_frame, "Total Terlambat", f"{total_late} mnt"
                ).grid(row=0, column=1, padx=4, sticky="ew")
        KPICard(kpi_frame, "Coaching Flag", str(len(coaching)),
                value_color=COLOR_WARN
                ).grid(row=0, column=2, padx=4, sticky="ew")
        KPICard(kpi_frame, "Teladan", teladan_name, value_color=COLOR_OK
                ).grid(row=0, column=3, padx=4, sticky="ew")

        # Top 5 + coaching side by side
        twin = ctk.CTkFrame(self.body, fg_color="transparent")
        twin.pack(fill="x", pady=(8, 0))
        twin.grid_columnconfigure(0, weight=1)
        twin.grid_columnconfigure(1, weight=1)

        top5_box = ctk.CTkFrame(twin, fg_color=COLOR_PANEL, corner_radius=8)
        top5_box.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        ctk.CTkLabel(top5_box, text="🔥 Top 5 Terlambat",
                     font=(FONT_FAMILY, 13, "bold")
                     ).pack(anchor="w", padx=12, pady=8)
        if not top5:
            ctk.CTkLabel(top5_box, text="Tidak ada keterlambatan.",
                         text_color="#94a3b8").pack(padx=12, pady=4)
        for r in top5:
            row = ctk.CTkFrame(top5_box, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=2)
            ctk.CTkLabel(row, text=f"{r['nama']} ({r['dept']})").pack(side="left")
            ctk.CTkLabel(row, text=f"{r['total_terlambat']} mnt",
                         text_color=COLOR_WARN).pack(side="right")

        coach_box = ctk.CTkFrame(twin, fg_color=COLOR_PANEL, corner_radius=8)
        coach_box.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        ctk.CTkLabel(coach_box, text="⚠ Butuh Coaching (>75 mnt)",
                     font=(FONT_FAMILY, 13, "bold")
                     ).pack(anchor="w", padx=12, pady=8)
        if not coaching:
            ctk.CTkLabel(coach_box, text="Tidak ada. ✓",
                         text_color="#94a3b8").pack(padx=12, pady=4)
        for r in coaching:
            row = ctk.CTkFrame(coach_box, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=2)
            ctk.CTkLabel(row, text=f"{r['nama']} · {r['total_terlambat']} mnt"
                         ).pack(side="left")

        # Ranking lengkap (compact list)
        rank_box = ctk.CTkFrame(self.body, fg_color=COLOR_PANEL, corner_radius=8)
        rank_box.pack(fill="both", expand=True, pady=(8, 0))
        ctk.CTkLabel(rank_box, text="📋 Ranking Lengkap",
                     font=(FONT_FAMILY, 13, "bold")
                     ).pack(anchor="w", padx=12, pady=(8, 4))
        # Header row
        hdr = ctk.CTkFrame(rank_box, fg_color="transparent")
        hdr.pack(fill="x", padx=12)
        for col, w in (("NAMA", 200), ("DEPT", 140), ("TERLAMBAT", 100),
                       ("HARI TELAT", 90), ("ISSUE", 70)):
            ctk.CTkLabel(hdr, text=col, font=(FONT_FAMILY, 10, "bold"),
                         text_color="#94a3b8", width=w, anchor="w"
                         ).pack(side="left")
        # Body
        inner = ctk.CTkScrollableFrame(rank_box, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=12, pady=4)
        for r in ranking:
            row = ctk.CTkFrame(inner, fg_color="transparent")
            row.pack(fill="x", pady=1)
            for val, w in (
                (r["nama"], 200), (r["dept"] or "-", 140),
                (f"{r['total_terlambat']} mnt", 100),
                (str(r["hari_telat"]), 90), (str(r["issue_count"]), 70),
            ):
                ctk.CTkLabel(row, text=val, font=(FONT_FAMILY, 12),
                             width=w, anchor="w").pack(side="left")

    def _on_print(self):
        start, end, label = self._period_range()
        out_dir = Path(tempfile.gettempdir())
        try:
            with get_connection(DB_PATH) as conn:
                html_path = render_dashboard_html(
                    conn, period_start=start, period_end=end,
                    period_label=label, out_dir=out_dir,
                )
            webbrowser.open(html_path.as_uri())
        except Exception as e:
            messagebox.showerror("Error generating PDF", str(e))
