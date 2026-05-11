import webbrowser
from datetime import date, timedelta
from pathlib import Path
import customtkinter as ctk

from src.config import DB_PATH
from src.db.connection import get_connection
from src.db.settings import get_setting
from src.core.insights import (
    terlambat_ranking, top_n_terlambat, coaching_flag, karyawan_teladan
)
from src.reports.html_renderer import render_dashboard_html
from src.ui.components.kpi_card import KPICard
from src.ui.theme import FONT_FAMILY, COLOR_OK, COLOR_WARN, COLOR_PANEL


class InsightsScreen(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        self._build()

    def _build(self):
        # Header + period selector
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        ctk.CTkLabel(header, text="Insights",
                     font=(FONT_FAMILY, 24, "bold")).pack(side="left")

        self.period_var = ctk.StringVar(value="Bulanan")
        ctk.CTkSegmentedButton(
            header, values=["Mingguan", "Bulanan"],
            variable=self.period_var, command=lambda _: self._reload(),
        ).pack(side="right", padx=12)

        ctk.CTkButton(header, text="📄 Cetak / Export PDF",
                      fg_color=COLOR_OK, text_color="#0a0a0a",
                      command=self._on_print).pack(side="right")

        # Body container — re-rendered on period change
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.grid(row=1, column=0, sticky="nsew")
        self.grid_rowconfigure(1, weight=1)
        self._reload()

    def _period_range(self) -> tuple[str, str, str]:
        """Resolve (start_iso, end_iso, label) based on Mingguan/Bulanan selection."""
        period = self.period_var.get() if hasattr(self, "period_var") else "Bulanan"

        if period == "Mingguan":
            # End date = most recent imported_at date, or today if no imports yet
            with get_connection(DB_PATH) as conn:
                row = conn.execute(
                    "SELECT MAX(tanggal) AS last_date FROM attendance_records"
                ).fetchone()
            anchor_iso = row["last_date"] if row and row["last_date"] else date.today().isoformat()
            anchor = date.fromisoformat(anchor_iso)
            start = anchor - timedelta(days=6)
            return (
                start.isoformat(),
                anchor.isoformat(),
                f"Minggu {start.strftime('%d')}-{anchor.strftime('%d %b %Y')}",
            )

        # Bulanan (default)
        with get_connection(DB_PATH) as conn:
            cm = get_setting(conn, "current_month")
        if cm and len(cm) == 7:
            year, month = map(int, cm.split("-"))
            from calendar import monthrange
            last_day = monthrange(year, month)[1]
            start = f"{year:04d}-{month:02d}-01"
            end = f"{year:04d}-{month:02d}-{last_day:02d}"
            return start, end, f"Bulanan ({cm})"
        # Fallback: last 30 days
        today = date.today()
        return (today - timedelta(days=30)).isoformat(), today.isoformat(), "Last 30 days"

    def _reload(self):
        for w in self.body.winfo_children():
            w.destroy()

        start, end, label = self._period_range()
        with get_connection(DB_PATH) as conn:
            ranking = terlambat_ranking(conn, start, end)
            top5 = top_n_terlambat(conn, start, end, 5)
            coaching = coaching_flag(conn, start, end)
            teladan = karyawan_teladan(conn, start, end)

        # KPI row
        kpi_frame = ctk.CTkFrame(self.body, fg_color="transparent")
        kpi_frame.pack(fill="x", pady=(0, 12))
        for i in range(4):
            kpi_frame.grid_columnconfigure(i, weight=1)

        total_late = sum(r["total_terlambat"] for r in ranking)
        teladan_name = teladan["nama"] if teladan else "-"

        KPICard(kpi_frame, "Total Terlambat", f"{total_late} mnt"
                ).grid(row=0, column=0, padx=4, sticky="ew")
        KPICard(kpi_frame, "Coaching Flag", str(len(coaching)),
                value_color=COLOR_WARN
                ).grid(row=0, column=1, padx=4, sticky="ew")
        KPICard(kpi_frame, "Top Late", f"{top5[0]['nama']} ({top5[0]['total_terlambat']})"
                if top5 else "-"
                ).grid(row=0, column=2, padx=4, sticky="ew")
        KPICard(kpi_frame, "Teladan", teladan_name, value_color=COLOR_OK
                ).grid(row=0, column=3, padx=4, sticky="ew")

        # Top 5 + coaching side by side
        twin = ctk.CTkFrame(self.body, fg_color="transparent")
        twin.pack(fill="both", expand=True, pady=(8, 0))
        twin.grid_columnconfigure(0, weight=1)
        twin.grid_columnconfigure(1, weight=1)

        top5_box = ctk.CTkFrame(twin, fg_color=COLOR_PANEL, corner_radius=8)
        top5_box.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        ctk.CTkLabel(top5_box, text="🔥 Top 5 Terlambat",
                     font=(FONT_FAMILY, 13, "bold")).pack(anchor="w", padx=12, pady=8)
        for r in top5:
            row = ctk.CTkFrame(top5_box, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=2)
            ctk.CTkLabel(row, text=f"{r['nama']} ({r['dept']})").pack(side="left")
            ctk.CTkLabel(row, text=f"{r['total_terlambat']} mnt",
                         text_color=COLOR_WARN).pack(side="right")

        coach_box = ctk.CTkFrame(twin, fg_color=COLOR_PANEL, corner_radius=8)
        coach_box.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        ctk.CTkLabel(coach_box, text="⚠ Butuh Coaching (>75 mnt)",
                     font=(FONT_FAMILY, 13, "bold")).pack(anchor="w", padx=12, pady=8)
        if not coaching:
            ctk.CTkLabel(coach_box, text="Tidak ada. ✓",
                         text_color="#94a3b8").pack(padx=12, pady=4)
        for r in coaching:
            row = ctk.CTkFrame(coach_box, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=2)
            ctk.CTkLabel(row, text=f"{r['nama']} · {r['total_terlambat']} mnt").pack(side="left")

    def _on_print(self):
        import tempfile
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
            from tkinter import messagebox
            messagebox.showerror("Error generating PDF", str(e))
