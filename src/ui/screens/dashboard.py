import tempfile
from pathlib import Path

import customtkinter as ctk
from tkinter import messagebox
from tkinter import ttk

from src.config import DB_PATH
from src.db.connection import get_connection
from src.db.settings import get_setting
from src.core.insights import (
    terlambat_ranking, top_n_terlambat, coaching_flag,
    karyawan_teladan_top_n, ranking_departemen, hari_paling_rawan,
)
from src.core.week_utils import weeks_in_month, full_month_range
from src.reports.html_renderer import render_dashboard_html
from src.ui.components.kpi_card import KPICard
from src.ui.components.week_nav import WeekNavBar
from src.ui.theme import (
    FONT_FAMILY, COLOR_OK, COLOR_WARN, COLOR_ACCENT, COLOR_PANEL,
    COLOR_TEXT, COLOR_TEXT_DIM,
)


class DashboardScreen(ctk.CTkFrame):
    """Dashboard analytics view.

    Static widget structure (panels, KPI cards, ranking table container) is
    built once in __init__. Tab/period switches only update the data inside
    those widgets, avoiding expensive Canvas/Scrollable recreations.

    Query results per (start, end) are memoized — switching back to a
    previously-viewed period is instant.
    """

    PANEL_H_REGULAR = 220
    PANEL_H_COACH = 360    # spans rows 1+2 in Mingguan (Dept + Hari combined)
    PANEL_H_HARI = 130     # compact, non-scrollable (max 5-6 weekdays)

    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        with get_connection(DB_PATH) as conn:
            self._current_month = get_setting(conn, "current_month") or ""

        # Per-(start, end) query cache. Reset each time the screen is
        # constructed (i.e., user navigates away and back), so writes in
        # other screens won't show stale data.
        self._query_cache: dict = {}

        # Refs to widgets that get TEXT updated on period change
        self._kpi_labels: dict = {}        # name -> CTkLabel for value
        self._kpi_label_period: ctk.CTkLabel | None = None
        self._panel_titles: dict = {}      # panel key -> CTkLabel for title
        self._panel_content: dict = {}     # panel key -> parent frame for rows
        self._panel_boxes: dict = {}       # panel key -> outer CTkFrame (for grid/grid_remove)
        self._setup_treeview_style()
        self._build_header()
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.grid(row=1, column=0, sticky="nsew")
        self._build_static_widgets()
        self._update_data()

    def _setup_treeview_style(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure(
            "Ranking.Treeview",
            background=COLOR_PANEL, fieldbackground=COLOR_PANEL,
            foreground=COLOR_TEXT, rowheight=24, borderwidth=0,
        )
        style.configure(
            "Ranking.Treeview.Heading",
            background="#2C1B47", foreground=COLOR_TEXT_DIM,
            relief="flat", font=(FONT_FAMILY, 10, "bold"),
        )

    # ──────────────────────────────────────────────────────────── Header

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 16))

        ctk.CTkLabel(
            header, text="Dashboard", font=(FONT_FAMILY, 24, "bold"),
            text_color=COLOR_TEXT,
        ).pack(side="left", padx=(0, 16))

        self.nav = WeekNavBar(
            header, current_month=self._current_month,
            on_change=self._on_period_change, initial="semua",
        )
        self.nav.pack(side="left")

        ctk.CTkButton(
            header, text="📄 Cetak / Export PDF",
            fg_color=COLOR_OK, text_color="#1E104E",
            command=self._on_print,
        ).pack(side="right", padx=(8, 0))

    # ──────────────────────────────────────────────────── Static widgets

    def _build_static_widgets(self):
        """Build all panels, KPI cards, and the ranking container ONCE."""
        # Body uses 2-column grid: left (60%) dense panels + right (40%) ranking
        self.body.grid_columnconfigure(0, weight=3)
        self.body.grid_columnconfigure(1, weight=2)
        self.body.grid_rowconfigure(1, weight=1)

        # ── KPI ROW ──
        kpi_frame = ctk.CTkFrame(self.body, fg_color="transparent")
        kpi_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        for i in range(3):
            kpi_frame.grid_columnconfigure(i, weight=1)

        def _kpi(parent, label_text, name, color):
            card = ctk.CTkFrame(parent, fg_color=COLOR_PANEL, corner_radius=8)
            ctk.CTkLabel(card, text=label_text.upper(),
                         font=(FONT_FAMILY, 10), text_color=COLOR_TEXT_DIM
                         ).pack(anchor="w", padx=14, pady=(12, 0))
            value_lbl = ctk.CTkLabel(
                card, text="—", font=(FONT_FAMILY, 22, "bold"),
                text_color=color,
            )
            value_lbl.pack(anchor="w", padx=14, pady=(0, 12))
            self._kpi_labels[name] = value_lbl
            return card

        _kpi(kpi_frame, "Periode", "periode", COLOR_TEXT).grid(
            row=0, column=0, padx=4, sticky="ew")
        _kpi(kpi_frame, "Total Terlambat", "total_terlambat", COLOR_ACCENT).grid(
            row=0, column=1, padx=4, sticky="ew")
        _kpi(kpi_frame, "Coaching Flag", "coaching_count", COLOR_WARN).grid(
            row=0, column=2, padx=4, sticky="ew")

        # ── LEFT: dense panel grid ──
        left = ctk.CTkFrame(self.body, fg_color="transparent")
        left.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
        left.grid_columnconfigure(0, weight=1)
        left.grid_columnconfigure(1, weight=1)

        def make_panel(parent, title, color, panel_key, fixed_height,
                       scrollable):
            box = ctk.CTkFrame(parent, fg_color=COLOR_PANEL, corner_radius=8,
                                height=fixed_height)
            box.grid_propagate(False)
            box.grid_columnconfigure(0, weight=1)
            box.grid_rowconfigure(1, weight=1)
            title_lbl = ctk.CTkLabel(
                box, text=title, font=(FONT_FAMILY, 12, "bold"),
                text_color=color,
            )
            title_lbl.grid(row=0, column=0, sticky="w", padx=10, pady=(8, 4))
            self._panel_titles[panel_key] = title_lbl

            if scrollable:
                content = ctk.CTkScrollableFrame(
                    box, fg_color="transparent", corner_radius=0,
                )
            else:
                content = ctk.CTkFrame(box, fg_color="transparent")
            content.grid(row=1, column=0, sticky="nsew", padx=4, pady=(0, 6))
            self._panel_content[panel_key] = content
            self._panel_boxes[panel_key] = box
            return box

        # Top 5 panels — bounded, non-scrollable
        make_panel(left, "🔥 Top 5 Terlambat", COLOR_ACCENT,
                   "late", self.PANEL_H_REGULAR, scrollable=False)
        make_panel(left, "🏆 Top 5 Teladan", COLOR_OK,
                   "teladan", self.PANEL_H_REGULAR, scrollable=False)
        # Coaching: taller, non-scrollable; only shown in Mingguan view
        make_panel(left, "⚠ Butuh Coaching", COLOR_WARN,
                   "coaching", self.PANEL_H_COACH, scrollable=False)
        # Dept ranking: non-scrollable (~4 depts, bounded)
        make_panel(left, "🏢 Ranking Departemen", COLOR_ACCENT,
                   "dept", self.PANEL_H_REGULAR, scrollable=False)
        # Hari Rawan: compact, non-scrollable (5-6 weekdays max)
        make_panel(left, "📅 Hari Paling Rawan", COLOR_WARN,
                   "hari", self.PANEL_H_HARI, scrollable=False)

        # Initial grid positions set by _apply_layout() in _update_data()

        # ── RIGHT: Ranking Lengkap (ttk.Treeview — native, scrollable) ──
        rank_box = ctk.CTkFrame(self.body, fg_color=COLOR_PANEL, corner_radius=8)
        rank_box.grid(row=1, column=1, sticky="nsew")
        ctk.CTkLabel(rank_box, text="📋 Ranking Lengkap",
                     font=(FONT_FAMILY, 13, "bold"), text_color=COLOR_TEXT
                     ).pack(anchor="w", padx=12, pady=(8, 4))

        cols = ["nama", "dept", "terlambat", "telat", "tidak_hadir"]
        widths = {"nama": 130, "dept": 100, "terlambat": 80,
                  "telat": 50, "tidak_hadir": 70}
        labels = {"nama": "Nama", "dept": "Dept", "terlambat": "Terlambat",
                  "telat": "Telat", "tidak_hadir": "Tdk Hadir"}

        self.rank_tree = ttk.Treeview(
            rank_box, columns=cols, show="headings",
            style="Ranking.Treeview", selectmode="none",
        )
        for c in cols:
            self.rank_tree.heading(c, text=labels[c])
            self.rank_tree.column(c, width=widths[c], anchor="w")
        self.rank_tree.pack(fill="both", expand=True, padx=12, pady=(4, 8))

    # ──────────────────────────────────────────────────── Period range helper

    def _period_range(self):
        if not self._current_month:
            from datetime import date, timedelta
            today = date.today()
            return (today - timedelta(days=30)).isoformat(), today.isoformat(), "Last 30 days"
        if self.nav.active == "semua":
            start, end = full_month_range(self._current_month)
            return start, end, f"Bulanan ({self._current_month})"
        try:
            num = int(self.nav.active.split("_")[1])
        except (IndexError, ValueError):
            num = 1
        for n, start, end in weeks_in_month(self._current_month):
            if n == num:
                return start, end, f"Minggu {n} ({start} → {end})"
        start, end = full_month_range(self._current_month)
        return start, end, f"Bulanan ({self._current_month})"

    def _dynamic_coaching_threshold(self, start_iso, end_iso):
        from datetime import date
        s = date.fromisoformat(start_iso)
        e = date.fromisoformat(end_iso)
        days = (e - s).days + 1
        weeks = max(1, (days + 6) // 7)
        return 75 * weeks

    # ──────────────────────────────────────────────────── Data updates

    def _on_period_change(self, _key):
        self._update_data()

    def _apply_layout(self, is_bulanan: bool):
        """Reposition the 5 left-side panels based on whether period is Bulanan.

        Bulanan (no Coaching panel — threshold scales by week, not meaningful monthly):
            [Top 5 Late]   [Top 5 Teladan]
            [Dept]         [Hari Rawan]

        Mingguan (Coaching shown, spans 2 rows on the left):
            [Top 5 Late]   [Top 5 Teladan]
            [Coaching ↕]   [Dept]
            [Coaching ↕]   [Hari Rawan]
        """
        late = self._panel_boxes["late"]
        teladan = self._panel_boxes["teladan"]
        coach = self._panel_boxes["coaching"]
        dept = self._panel_boxes["dept"]
        hari = self._panel_boxes["hari"]

        # Row 0 is identical in both layouts
        late.grid(row=0, column=0, sticky="nsew", padx=(0, 4), pady=(0, 4))
        teladan.grid(row=0, column=1, sticky="nsew", padx=(4, 0), pady=(0, 4))

        if is_bulanan:
            coach.grid_remove()
            dept.grid(row=1, column=0, rowspan=1, columnspan=1, sticky="nsew",
                      padx=(0, 4), pady=4)
            hari.grid(row=1, column=1, rowspan=1, columnspan=1, sticky="nsew",
                      padx=(4, 0), pady=4)
        else:
            coach.grid(row=1, column=0, rowspan=2, columnspan=1, sticky="nsew",
                       padx=(0, 4), pady=(4, 0))
            dept.grid(row=1, column=1, rowspan=1, columnspan=1, sticky="nsew",
                      padx=(4, 0), pady=(4, 2))
            hari.grid(row=2, column=1, rowspan=1, columnspan=1, sticky="nsew",
                      padx=(4, 0), pady=(2, 0))

    def _query(self, start, end):
        """Memoized data fetch. Returns a dict of pre-computed result lists."""
        key = (start, end)
        if key in self._query_cache:
            return self._query_cache[key]

        threshold = self._dynamic_coaching_threshold(start, end)
        with get_connection(DB_PATH) as conn:
            data = {
                "ranking": [dict(r) for r in terlambat_ranking(conn, start, end)],
                "top5_late": [dict(r) for r in top_n_terlambat(conn, start, end, 5)],
                "coaching": [dict(r) for r in coaching_flag(conn, start, end, threshold=threshold)],
                "top5_teladan": [dict(r) for r in karyawan_teladan_top_n(conn, start, end, 5)],
                "dept_rows": [dict(r) for r in ranking_departemen(conn, start, end)],
                "day_rows": [dict(r) for r in hari_paling_rawan(conn, start, end)],
                "threshold": threshold,
            }
        self._query_cache[key] = data
        return data

    def _clear_panel(self, panel_key):
        """Wipe row widgets inside a panel's content frame (preserve container)."""
        content = self._panel_content[panel_key]
        for w in content.winfo_children():
            w.destroy()

    def _two_col_row(self, parent, left_text, right_text, right_color):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=6, pady=1)
        ctk.CTkLabel(row, text=left_text, font=(FONT_FAMILY, 11),
                     text_color=COLOR_TEXT, anchor="w").pack(side="left")
        ctk.CTkLabel(row, text=right_text, font=(FONT_FAMILY, 11),
                     text_color=right_color, anchor="e").pack(side="right")

    def _empty(self, parent, text):
        ctk.CTkLabel(parent, text=text, text_color=COLOR_TEXT_DIM,
                     font=(FONT_FAMILY, 11)).pack(padx=8, pady=4)

    def _update_data(self):
        start, end, label = self._period_range()
        is_bulanan = (self.nav.active == "semua")
        self._apply_layout(is_bulanan)

        data = self._query(start, end)
        total_late = sum(r["total_terlambat"] for r in data["ranking"])
        threshold = data["threshold"]

        # KPI updates (just text — labels are reused)
        self._kpi_labels["periode"].configure(text=label)
        self._kpi_labels["total_terlambat"].configure(text=f"{total_late} mnt")
        self._kpi_labels["coaching_count"].configure(text=str(len(data["coaching"])))

        # Coaching panel title with dynamic threshold
        self._panel_titles["coaching"].configure(
            text=f"⚠ Butuh Coaching (>{threshold} mnt)"
        )

        # ── Top 5 Late ──
        self._clear_panel("late")
        content = self._panel_content["late"]
        if not data["top5_late"]:
            self._empty(content, "Tidak ada keterlambatan.")
        else:
            for r in data["top5_late"]:
                self._two_col_row(content, r["nama"],
                                  f"{r['total_terlambat']} mnt", COLOR_ACCENT)

        # ── Top 5 Teladan ──
        self._clear_panel("teladan")
        content = self._panel_content["teladan"]
        if not data["top5_teladan"]:
            self._empty(content, "Belum ada data.")
        else:
            medals = ["🥇", "🥈", "🥉", "4.", "5."]
            for idx, r in enumerate(data["top5_teladan"]):
                self._two_col_row(content, f"{medals[idx]} {r['nama']}",
                                  f"skor {r['score']}", COLOR_OK)

        # ── Coaching ──
        self._clear_panel("coaching")
        content = self._panel_content["coaching"]
        if not data["coaching"]:
            self._empty(content, "Tidak ada. ✓")
        else:
            for r in data["coaching"]:
                self._two_col_row(content, r["nama"],
                                  f"{r['total_terlambat']} mnt", COLOR_WARN)

        # ── Departemen ──
        self._clear_panel("dept")
        content = self._panel_content["dept"]
        if not data["dept_rows"]:
            self._empty(content, "Belum ada data.")
        else:
            for r in data["dept_rows"]:
                self._two_col_row(content,
                                  f"{r['dept']} ({r['pegawai_count']})",
                                  f"{r['total_terlambat']} mnt", COLOR_ACCENT)

        # ── Hari Rawan ──
        self._clear_panel("hari")
        content = self._panel_content["hari"]
        if not data["day_rows"]:
            self._empty(content, "Belum ada data harian.")
        else:
            for r in data["day_rows"]:
                self._two_col_row(content, r["hari"],
                                  f"{r['terlambat_count']} hari telat",
                                  COLOR_WARN)

        # ── Ranking Lengkap (right) — Treeview ──
        self.rank_tree.delete(*self.rank_tree.get_children())
        for r in data["ranking"]:
            self.rank_tree.insert("", "end", values=(
                r["nama"], r["dept"] or "-",
                f"{r['total_terlambat']} mnt",
                r["hari_telat"], r["tidak_hadir"],
            ))

    # ─────────────────────────────────────────────────────────── Print

    def _on_print(self):
        from src.ui.components.print_dialog import PrintOptionsDialog
        PrintOptionsDialog(
            self.winfo_toplevel(),
            on_submit=self._do_print,
        )

    def _do_print(self, sections, theme):
        from src.ui.browser_launcher import open_html_in_browser
        from src.ui.components.toast import show_success_toast

        start, end, label = self._period_range()
        dynamic_threshold = self._dynamic_coaching_threshold(start, end)
        out_dir = Path(tempfile.gettempdir())
        try:
            with get_connection(DB_PATH) as conn:
                html_path = render_dashboard_html(
                    conn, period_start=start, period_end=end,
                    period_label=label, out_dir=out_dir,
                    template_name=theme, sections=sections,
                    threshold=dynamic_threshold,
                )
        except Exception as e:
            messagebox.showerror("Error generating PDF", str(e))
            return

        success, browser_name = open_html_in_browser(html_path)
        if success:
            show_success_toast(
                self.winfo_toplevel(),
                title="Dashboard Dibuka",
                message=(
                    f"Dashboard {label} dibuka di {browser_name}.\n"
                    f"Tema: {theme} · Gunakan Ctrl+P untuk Save as PDF."
                ),
            )
        else:
            messagebox.showwarning(
                "Browser tidak ditemukan",
                f"Tidak menemukan browser (Chrome/Edge/Firefox).\n\n"
                f"File HTML tersimpan di:\n{html_path}\n\n"
                "Buka manual: klik kanan → Open with → pilih browser."
            )
