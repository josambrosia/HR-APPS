import tempfile
from pathlib import Path

import customtkinter as ctk
from tkinter import messagebox
from tkinter import ttk

from src.config import DB_PATH
from src.db.connection import get_connection
from src.db.holidays import working_days_count
from src.db.settings import get_setting
from src.core.insights import (
    terlambat_ranking, top_n_terlambat, coaching_flag,
    karyawan_teladan_top_n, ranking_departemen, hari_paling_rawan,
)
from src.core.week_utils import weeks_in_month, full_month_range
from src.reports.html_renderer import render_dashboard_html
from src.ui.components.week_nav import WeekNavBar
from src.core.session_state import period_state
from src.ui.theme import (
    FONT_FAMILY, FONT_MONO,
    COLOR_BG, COLOR_SURFACE, COLOR_SURFACE_HIGH,
    COLOR_BORDER,
    COLOR_ACCENT, COLOR_ACCENT_HOVER,
    COLOR_SECONDARY,
    COLOR_INFO, COLOR_SUCCESS, COLOR_WARN,
    COLOR_TEXT, COLOR_TEXT_DIM, COLOR_TEXT_MUTED, COLOR_TEXT_DISABLED,
    FONT_DISPLAY, FONT_SUBHEAD,
    FONT_BODY_BOLD, FONT_SMALL, FONT_LABEL,
    FONT_MONO_DATA, FONT_MONO_SMALL,
    SPACE_XS, SPACE_SM, SPACE_MD, SPACE_LG,
    RADIUS_MD,
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
        self._panel_subtitles: dict = {}   # panel key -> CTkLabel for subtitle (optional)
        self._panel_content: dict = {}     # panel key -> parent frame for rows
        self._panel_boxes: dict = {}       # panel key -> outer CTkFrame (for grid/grid_remove)
        self._panel_rows: dict[str, list[dict]] = {}   # panel_key -> [{"frame", "left", "right"}, ...]
        self._panel_empty: dict[str, ctk.CTkLabel] = {}  # panel_key -> empty-state label
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
            background=COLOR_SURFACE,
            fieldbackground=COLOR_SURFACE,
            foreground=COLOR_TEXT,
            rowheight=24,
            borderwidth=0,
            font=FONT_SMALL,
        )
        style.configure(
            "Ranking.Treeview.Heading",
            background=COLOR_SURFACE_HIGH,
            foreground=COLOR_TEXT_MUTED,
            relief="flat",
            font=(FONT_FAMILY, 9, "bold"),
        )
        style.map(
            "Ranking.Treeview",
            background=[("selected", COLOR_SURFACE_HIGH)],
            foreground=[("selected", COLOR_TEXT)],
        )

    # ──────────────────────────────────────────────────────────── Header

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 16))

        ctk.CTkLabel(
            header, text="Dashboard",
            font=FONT_DISPLAY,
            text_color=COLOR_TEXT,
        ).pack(side="left", padx=(0, 0))

        ctk.CTkLabel(
            header, text="/ insights",
            font=FONT_MONO_SMALL,
            text_color=COLOR_TEXT_DISABLED,
        ).pack(side="left", padx=(SPACE_SM, SPACE_LG), pady=(SPACE_SM, 0))

        self.nav = WeekNavBar(
            header, current_month=self._current_month,
            on_change=self._on_period_change, initial=period_state.get(),
        )
        self.nav.pack(side="left")

        ctk.CTkButton(
            header, text="📄 Cetak / Export PDF",
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
            text_color=COLOR_BG,
            font=FONT_BODY_BOLD,
            command=self._on_print,
        ).pack(side="right", padx=(SPACE_SM, 0))

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

        def _kpi(parent, label_text, name, color, mono=False):
            card = ctk.CTkFrame(
                parent, fg_color=COLOR_SURFACE,
                border_width=1, border_color=COLOR_BORDER,
                corner_radius=RADIUS_MD,
            )
            ctk.CTkLabel(
                card, text=label_text.upper(),
                font=FONT_LABEL, text_color=COLOR_TEXT_MUTED,
            ).pack(anchor="w", padx=SPACE_LG, pady=(SPACE_MD, 0))
            value_lbl = ctk.CTkLabel(
                card, text="—",
                font=(FONT_MONO, 24, "bold") if mono else (FONT_FAMILY, 17, "bold"),
                text_color=color,
            )
            value_lbl.pack(anchor="w", padx=SPACE_LG, pady=(0, SPACE_MD))
            self._kpi_labels[name] = value_lbl
            return card

        _kpi(kpi_frame, "Periode", "periode", COLOR_INFO, mono=False).grid(
            row=0, column=0, padx=SPACE_XS, sticky="ew")
        _kpi(kpi_frame, "Total Terlambat", "total_terlambat", COLOR_WARN, mono=True).grid(
            row=0, column=1, padx=SPACE_XS, sticky="ew")
        _kpi(kpi_frame, "Coaching Flag", "coaching_count", COLOR_WARN, mono=True).grid(
            row=0, column=2, padx=SPACE_XS, sticky="ew")

        # ── LEFT: dense panel grid ──
        left = ctk.CTkFrame(self.body, fg_color="transparent")
        left.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
        left.grid_columnconfigure(0, weight=1)
        left.grid_columnconfigure(1, weight=1)

        def make_panel(parent, title, color, panel_key, fixed_height, with_subtitle=False):
            box = ctk.CTkFrame(
                parent, fg_color=COLOR_SURFACE,
                border_width=1, border_color=COLOR_BORDER,
                corner_radius=RADIUS_MD,
                height=fixed_height,
            )
            box.grid_propagate(False)
            box.grid_columnconfigure(0, weight=1)
            title_lbl = ctk.CTkLabel(
                box, text=title,
                font=FONT_SUBHEAD,
                text_color=color,
            )
            title_lbl.grid(row=0, column=0, sticky="w", padx=SPACE_MD, pady=(SPACE_SM, SPACE_XS))
            self._panel_titles[panel_key] = title_lbl

            if with_subtitle:
                subtitle_lbl = ctk.CTkLabel(
                    box, text="",
                    font=FONT_SMALL,
                    text_color=COLOR_TEXT_MUTED,
                    anchor="w", justify="left",
                )
                subtitle_lbl.grid(row=1, column=0, sticky="w", padx=SPACE_MD, pady=(0, SPACE_XS))
                self._panel_subtitles[panel_key] = subtitle_lbl
                box.grid_rowconfigure(2, weight=1)
                content_row = 2
            else:
                box.grid_rowconfigure(1, weight=1)
                content_row = 1

            content = ctk.CTkFrame(box, fg_color="transparent")
            content.grid(row=content_row, column=0, sticky="nsew", padx=SPACE_XS, pady=(0, SPACE_SM))
            self._panel_content[panel_key] = content
            self._panel_boxes[panel_key] = box
            return box

        # Top 5 panels — bounded
        make_panel(left, "🔥 Top 5 Terlambat", COLOR_TEXT,
                   "late", self.PANEL_H_REGULAR)
        make_panel(left, "🏆 Top 5 Teladan", COLOR_SECONDARY,
                   "teladan", self.PANEL_H_REGULAR)
        # Coaching: taller, non-scrollable; only shown in Mingguan view
        make_panel(left, "⚠ Butuh Coaching", COLOR_WARN,
                   "coaching", self.PANEL_H_COACH, with_subtitle=True)
        # Dept ranking: non-scrollable (~4 depts, bounded)
        make_panel(left, "🏢 Ranking Departemen", COLOR_TEXT,
                   "dept", self.PANEL_H_REGULAR)
        # Hari Rawan: compact, non-scrollable (5-6 weekdays max)
        make_panel(left, "📅 Hari Paling Rawan", COLOR_TEXT,
                   "hari", self.PANEL_H_HARI)

        # Pre-build widget pools for each panel (eliminates destroy/rebuild on tab switch)
        self._build_panel_pool("late", size=5, empty_text="Tidak ada keterlambatan.")
        self._build_panel_pool("teladan", size=5, empty_text="Belum ada data.")
        self._build_panel_pool("coaching", size=20, empty_text="Tidak ada. ✓")
        self._build_panel_pool("dept", size=8, empty_text="Belum ada data.")
        self._build_panel_pool("hari", size=7, empty_text="Belum ada data harian.")

        # Initial grid positions set by _apply_layout() in _update_data()

        # ── RIGHT: Ranking Lengkap (ttk.Treeview — native, scrollable) ──
        rank_box = ctk.CTkFrame(
            self.body, fg_color=COLOR_SURFACE,
            border_width=1, border_color=COLOR_BORDER,
            corner_radius=RADIUS_MD,
        )
        rank_box.grid(row=1, column=1, sticky="nsew")
        ctk.CTkLabel(
            rank_box, text="📋 Ranking Lengkap",
            font=FONT_SUBHEAD,
            text_color=COLOR_TEXT,
        ).pack(anchor="w", padx=SPACE_MD, pady=(SPACE_SM, SPACE_XS))

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

    def _make_pool_row(self, panel_key: str) -> dict:
        """Create one pool row (frame + left/right labels). Created hidden — packed by _populate_pool."""
        parent = self._panel_content[panel_key]
        frame = ctk.CTkFrame(parent, fg_color="transparent", height=22)
        frame.pack_propagate(False)
        left = ctk.CTkLabel(
            frame, text="", font=FONT_SMALL,
            text_color=COLOR_TEXT, anchor="w",
        )
        right = ctk.CTkLabel(
            frame, text="", font=FONT_MONO_DATA,
            text_color=COLOR_TEXT, anchor="e",
        )
        left.pack(side="left", padx=(SPACE_SM, 0))
        right.pack(side="right", padx=(0, SPACE_SM))

        # Hover handlers — subtle bg tint
        def _on_enter(_e):
            frame.configure(fg_color=COLOR_SURFACE_HIGH)

        def _on_leave(_e):
            frame.configure(fg_color="transparent")

        for w in (frame, left, right):
            w.bind("<Enter>", _on_enter)
            w.bind("<Leave>", _on_leave)

        return {"frame": frame, "left": left, "right": right}

    def _build_panel_pool(self, panel_key: str, size: int, empty_text: str) -> None:
        """Pre-create row pool + empty-state label for a panel."""
        parent = self._panel_content[panel_key]
        self._panel_empty[panel_key] = ctk.CTkLabel(
            parent, text=empty_text, text_color=COLOR_TEXT_DIM,
            font=FONT_SMALL,
        )
        self._panel_rows[panel_key] = [
            self._make_pool_row(panel_key) for _ in range(size)
        ]

    def _populate_pool(self, panel_key: str, items: list, formatter) -> None:
        """Reconfigure pool to show `items`. formatter(item) -> (left_text, right_text, right_color)."""
        rows = self._panel_rows[panel_key]
        empty_lbl = self._panel_empty[panel_key]

        # Hide everything first to guarantee correct stack order
        empty_lbl.pack_forget()
        for r in rows:
            r["frame"].pack_forget()

        if not items:
            empty_lbl.pack(padx=8, pady=4)
            return

        # Auto-grow pool if dataset exceeds preallocated size (rare)
        while len(rows) < len(items):
            rows.append(self._make_pool_row(panel_key))

        # Pack visible rows in order, with text + color updated
        for i, item in enumerate(items):
            lt, rt, rc = formatter(item)
            rows[i]["left"].configure(text=lt)
            rows[i]["right"].configure(text=rt, text_color=rc)
            rows[i]["frame"].pack(fill="x", padx=6, pady=1)

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
        """Compute coaching threshold for the period.

        Returns dict {'daily': int, 'working_days': int, 'effective': int}.
        Effective = daily quota × distinct Hari Kerja dates in [start, end].
        """
        with get_connection(DB_PATH) as conn:
            daily_raw = get_setting(conn, "coaching_threshold_per_day", default="15")
            try:
                daily = int(daily_raw)
            except (TypeError, ValueError):
                daily = 15
            working_days = working_days_count(conn, start_iso, end_iso)
        return {
            "daily": daily,
            "working_days": working_days,
            "effective": daily * working_days,
        }

    # ──────────────────────────────────────────────────── Data updates

    def _on_period_change(self, _key):
        period_state.set(_key)
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

        threshold_info = self._dynamic_coaching_threshold(start, end)
        with get_connection(DB_PATH) as conn:
            data = {
                "ranking": [dict(r) for r in terlambat_ranking(conn, start, end)],
                "top5_late": [dict(r) for r in top_n_terlambat(conn, start, end, 5)],
                "coaching": [dict(r) for r in coaching_flag(conn, start, end, threshold=threshold_info["effective"])],
                "top5_teladan": [dict(r) for r in karyawan_teladan_top_n(conn, start, end, 5)],
                "dept_rows": [dict(r) for r in ranking_departemen(conn, start, end)],
                "day_rows": [dict(r) for r in hari_paling_rawan(conn, start, end)],
                "threshold": threshold_info,
            }
        self._query_cache[key] = data
        return data

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

        # Coaching panel title + subtitle with dynamic threshold
        if threshold["working_days"] > 0:
            self._panel_titles["coaching"].configure(
                text=f"⚠ Butuh Coaching (>{threshold['effective']} mnt)"
            )
            self._panel_subtitles["coaching"].configure(
                text=f"{threshold['daily']} mnt/hari × {threshold['working_days']} hari kerja"
            )
        else:
            self._panel_titles["coaching"].configure(text="⚠ Butuh Coaching")
            self._panel_subtitles["coaching"].configure(
                text="Belum ada data hari kerja periode ini."
            )

        # ── Top 5 Late ──
        self._populate_pool(
            "late", data["top5_late"],
            lambda r: (r["nama"], f"{r['total_terlambat']} mnt", COLOR_WARN),
        )

        # ── Top 5 Teladan (medals require index → wrap with enumerate) ──
        medals = ["🥇", "🥈", "🥉", "4.", "5."]
        teladan_indexed = list(enumerate(data["top5_teladan"]))
        self._populate_pool(
            "teladan", teladan_indexed,
            lambda iv: (f"{medals[iv[0]]} {iv[1]['nama']}",
                        f"skor {iv[1]['score']}", COLOR_SUCCESS),
        )

        # ── Coaching ──
        self._populate_pool(
            "coaching", data["coaching"],
            lambda r: (r["nama"], f"{r['total_terlambat']} mnt", COLOR_WARN),
        )

        # ── Departemen ──
        self._populate_pool(
            "dept", data["dept_rows"],
            lambda r: (f"{r['dept']} ({r['pegawai_count']})",
                       f"{r['total_terlambat']} mnt", COLOR_WARN),
        )

        # ── Hari Rawan ──
        self._populate_pool(
            "hari", data["day_rows"],
            lambda r: (r["hari"], f"{r['terlambat_count']} hari telat", COLOR_WARN),
        )

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

    def _do_print(self, sections):
        from src.ui.browser_launcher import open_html_in_browser
        from src.ui.components.toast import show_success_toast

        start, end, label = self._period_range()
        threshold_info = self._dynamic_coaching_threshold(start, end)
        out_dir = Path(tempfile.gettempdir())
        try:
            with get_connection(DB_PATH) as conn:
                html_path = render_dashboard_html(
                    conn, period_start=start, period_end=end,
                    period_label=label, out_dir=out_dir,
                    sections=sections,
                    threshold_info=threshold_info,
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
                    f"Gunakan Ctrl+P untuk Save as PDF."
                ),
            )
        else:
            messagebox.showwarning(
                "Browser tidak ditemukan",
                f"Tidak menemukan browser (Chrome/Edge/Firefox).\n\n"
                f"File HTML tersimpan di:\n{html_path}\n\n"
                "Buka manual: klik kanan → Open with → pilih browser."
            )
