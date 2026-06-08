"""Coaching screen — weekly view of pegawai over lateness threshold with
one-click toggle to mark coached and optional notes panel."""
from tkinter import ttk
import customtkinter as ctk

from src.config import DB_PATH
from src.core.session_state import period_state
from src.core.week_utils import weeks_in_month
from src.db.coaching import (
    list_coaching_for_week, mark_coached, unmark_coached,
    get_coaching_notes, update_notes,
)
from src.db.connection import get_connection
from src.db.holidays import working_days_count
from src.db.settings import get_setting
from src.ui.components.kpi_card import KPICard
from src.ui.components.week_nav import WeekNavBar
from src.ui.theme import (
    FONT_FAMILY,
    COLOR_BG, COLOR_SURFACE, COLOR_SURFACE_HIGH,
    COLOR_BORDER,
    COLOR_ACCENT, COLOR_ACCENT_HOVER,
    COLOR_INFO, COLOR_SUCCESS, COLOR_WARN,
    COLOR_TEXT, COLOR_TEXT_MUTED,
    COLOR_ROW_TINT_SUDAH, COLOR_ROW_TINT_BELUM,
    FONT_DISPLAY,
    FONT_BODY, FONT_BODY_BOLD, FONT_SMALL,
    SPACE_XS, SPACE_SM, SPACE_MD, SPACE_LG,
    RADIUS_MD,
)


class CoachingScreen(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self.grid_columnconfigure(0, weight=2)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=1)

        with get_connection(DB_PATH) as conn:
            self._current_month = get_setting(conn, "current_month") or ""
            daily_raw = get_setting(conn, "coaching_threshold_per_day") or "15"
            try:
                self._daily_threshold = int(daily_raw)
            except ValueError:
                self._daily_threshold = 15

        self.selected_row = None  # dict from _row_cache when row is selected
        self._row_cache = {}      # iid -> row dict

        self._setup_treeview_style()
        self._build_header()
        self._build_stats()
        self._build_table_and_panel()
        self._reload()

    def _setup_treeview_style(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure(
            "Coaching.Treeview",
            background=COLOR_SURFACE, fieldbackground=COLOR_SURFACE,
            foreground=COLOR_TEXT, rowheight=24, borderwidth=0,
            font=FONT_SMALL,
        )
        style.configure(
            "Coaching.Treeview.Heading",
            background=COLOR_SURFACE_HIGH, foreground=COLOR_TEXT_MUTED,
            relief="flat", font=(FONT_FAMILY, 9, "bold"),
        )
        # Phase 4a: drop lavender selection workaround (was commit 3af2277).
        # New semantic palette: Sudah=emerald, Belum=rose. COLOR_SURFACE_HIGH
        # is now a clean neutral hover that doesn't conflict with either.
        style.map(
            "Coaching.Treeview",
            background=[("selected", COLOR_SURFACE_HIGH)],
            foreground=[("selected", COLOR_TEXT)],
        )

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, SPACE_MD))
        ctk.CTkLabel(header, text="🎯 Coaching",
                     font=FONT_DISPLAY,
                     text_color=COLOR_TEXT).pack(side="left", padx=(0, SPACE_LG))
        self.nav = WeekNavBar(
            header, current_month=self._current_month,
            on_change=self._on_period_change, initial=period_state.get(),
            include_all=False,
        )
        self.nav.pack(side="left")

    def _on_period_change(self, _key):
        period_state.set(_key)
        self._reload()

    def _build_stats(self):
        self.stats = ctk.CTkFrame(self, fg_color="transparent")
        self.stats.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, SPACE_MD))
        for i in range(4):
            self.stats.grid_columnconfigure(i, weight=1)
        self._stats_cards = []

    def _render_stats(self, rows):
        for c in self._stats_cards:
            c.destroy()
        self._stats_cards = []

        total = len(rows)
        sudah = sum(1 for r in rows if r["is_coached"])
        belum = total - sudah
        if total > 0:
            coverage_pct = round(sudah / total * 100)
            coverage = f"{coverage_pct}%"
            # Conditional: emerald if > 75%, rose otherwise. Phase 4a drops
            # the COLOR_OK==COLOR_WARN workaround (now distinct emerald vs rose).
            coverage_color = COLOR_SUCCESS if coverage_pct > 75 else COLOR_WARN
        else:
            coverage = "—"
            coverage_color = COLOR_TEXT_MUTED

        # Semantic colors per JTS palette (commit 59446f2 orange Belum hack
        # is gone — rose and emerald are now distinct tokens):
        #   Total  → white (neutral)
        #   Sudah  → emerald (success)
        #   Belum  → rose (warn)
        #   Cov %  → conditional emerald/rose
        cards = [
            ("Total", str(total), COLOR_TEXT),
            ("Sudah", str(sudah), COLOR_SUCCESS),
            ("Belum", str(belum), COLOR_WARN),
            ("Coverage", coverage, coverage_color),
        ]
        for i, (label, val, color) in enumerate(cards):
            c = KPICard(self.stats, label, val, value_color=color)
            c.grid(row=0, column=i, padx=SPACE_XS, sticky="ew")
            self._stats_cards.append(c)

    def _build_table_and_panel(self):
        left = ctk.CTkFrame(self, fg_color="transparent")
        left.grid(row=2, column=0, sticky="nsew", padx=(0, SPACE_MD))
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(0, weight=1)

        cols = ["nama", "dept", "terlambat", "status"]
        widths = {"nama": 150, "dept": 110, "terlambat": 100, "status": 130}
        labels = {"nama": "Nama", "dept": "Dept", "terlambat": "Terlambat",
                  "status": "Status"}

        self.tree = ttk.Treeview(
            left, columns=cols, show="headings",
            style="Coaching.Treeview", selectmode="browse", height=12,
        )
        for c in cols:
            self.tree.heading(c, text=labels[c])
            self.tree.column(c, width=widths[c], anchor="w")
        # Tag-based row tinting per JTS semantic palette.
        # Sudah → emerald-tinted bg (rgba(16,185,129,.15)) + emerald fg.
        # Belum → rose-tinted bg (rgba(244,63,94,.15)) + rose fg.
        self.tree.tag_configure("sudah", background=COLOR_ROW_TINT_SUDAH, foreground=COLOR_SUCCESS)
        self.tree.tag_configure("belum", background=COLOR_ROW_TINT_BELUM, foreground=COLOR_WARN)
        self.tree.grid(row=0, column=0, sticky="nsew")
        # Selection event drives the right-panel; toggle is done via the
        # big button in the panel (inline AKSI column was too small/cramped).
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        right = ctk.CTkFrame(
            self, fg_color=COLOR_SURFACE,
            border_width=1, border_color=COLOR_BORDER,
            corner_radius=RADIUS_MD,
        )
        right.grid(row=2, column=1, sticky="nsew")
        self.right = right
        self._build_panel_empty()

    def _build_panel_empty(self):
        for w in self.right.winfo_children():
            w.destroy()
        ctk.CTkLabel(
            self.right,
            text="Pilih baris pegawai\nuntuk tandai sudah coaching\natau tulis catatan.",
            justify="center",
            font=FONT_BODY, text_color=COLOR_TEXT_MUTED
        ).pack(pady=80, padx=SPACE_LG)

    def _active_range(self):
        """Return (start, end, num) for the currently selected week pill."""
        key = self.nav.active
        try:
            num = int(key.split("_")[1])
        except (IndexError, ValueError):
            num = 1
        if not self._current_month:
            return None, None, num
        for n, start, end in weeks_in_month(self._current_month):
            if n == num:
                return start, end, num
        return None, None, num

    def _reload(self):
        start, end, _num = self._active_range()
        self._row_cache = {}
        for item in self.tree.get_children():
            self.tree.delete(item)

        if not start:
            self._render_stats([])
            return

        with get_connection(DB_PATH) as conn:
            working_days = working_days_count(conn, start, end)
            if working_days == 0:
                self._render_stats([])
                return
            effective = self._daily_threshold * working_days
            raw_rows = list_coaching_for_week(
                conn, week_start=start, week_end=end,
                threshold_minutes=effective,
            )
        rows = [dict(r) for r in raw_rows]
        self._render_stats(rows)

        for r in rows:
            iid = str(r["employee_id"])
            self._row_cache[iid] = r
            is_coached = bool(r["is_coached"])
            # Traffic-light style for high-glance readability:
            # 🟢 SUDAH (done) / 🔴 BELUM (pending). Combined with row tag
            # tints (rose for Belum, emerald for Sudah), status is
            # recognizable from across the table.
            status_text = "🟢 SUDAH" if is_coached else "🔴 BELUM"
            tag = "sudah" if is_coached else "belum"
            self.tree.insert(
                "", "end", iid=iid,
                values=(
                    r["nama"], r["dept"] or "-",
                    f"{r['total_terlambat']} mnt",
                    status_text,
                ),
                tags=(tag,),
            )

    def _toggle_row(self, iid: str):
        row = self._row_cache.get(iid)
        if not row:
            return
        start, _end, _num = self._active_range()
        if not start:
            return
        with get_connection(DB_PATH) as conn:
            if row["is_coached"]:
                unmark_coached(conn, employee_id=row["employee_id"], week_start=start)
            else:
                mark_coached(conn, employee_id=row["employee_id"], week_start=start)
        self._reload()
        # Re-select to keep panel in sync if the row is still visible
        if iid in self.tree.get_children():
            self.tree.selection_set(iid)

    def _on_select(self, _evt):
        sel = self.tree.selection()
        if not sel:
            return
        iid = sel[0]
        row = self._row_cache.get(iid)
        if row:
            self.selected_row = row
            self._build_panel_for(row)

    def _build_panel_for(self, row):
        for w in self.right.winfo_children():
            w.destroy()

        start, end, num = self._active_range()
        info_lines = [
            f"{row['nama']} ({row['dept'] or '-'})",
            f"Minggu {num} ({start} → {end})",
            f"Total terlambat: {row['total_terlambat']} mnt",
        ]
        ctk.CTkLabel(self.right, text="\n".join(info_lines), justify="left",
                     font=FONT_BODY, text_color=COLOR_TEXT
                     ).pack(anchor="w", padx=SPACE_LG, pady=(SPACE_LG, SPACE_MD))

        is_coached = bool(row["is_coached"])
        # Phase 4a: emerald for Sudah, rose for Belum (orange workaround
        # from commit 59446f2 is gone — they're now distinct semantic tokens).
        status_color = COLOR_SUCCESS if is_coached else COLOR_WARN
        status_lines = ["Status: " + ("🟢 SUDAH COACHING" if is_coached else "🔴 BELUM COACHING")]
        if is_coached and row.get("coached_at"):
            status_lines.append(f"Tercatat: {row['coached_at']}")
        ctk.CTkLabel(self.right, text="\n".join(status_lines), justify="left",
                     font=FONT_SMALL, text_color=status_color
                     ).pack(anchor="w", padx=SPACE_LG, pady=(0, SPACE_MD))

        ctk.CTkLabel(self.right, text="Catatan (opsional):",
                     font=FONT_SMALL, text_color=COLOR_TEXT_MUTED
                     ).pack(anchor="w", padx=SPACE_LG)

        notes_box = ctk.CTkTextbox(
            self.right, width=300, height=110,
            fg_color=COLOR_SURFACE_HIGH, border_width=1,
            border_color=COLOR_BORDER, text_color=COLOR_TEXT,
            font=FONT_BODY,
        )
        notes_box.pack(anchor="w", padx=SPACE_LG, pady=(SPACE_XS, SPACE_SM))

        if is_coached:
            existing = ""
            with get_connection(DB_PATH) as conn:
                existing = get_coaching_notes(
                    conn, employee_id=row["employee_id"], week_start=start,
                ) or ""
            notes_box.insert("1.0", existing)
            save_btn = ctk.CTkButton(
                self.right, text="Simpan Catatan",
                fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
                text_color=COLOR_BG, width=300, font=FONT_BODY_BOLD,
                command=lambda: self._on_save_notes(row, notes_box.get("1.0", "end").strip()),
            )
            save_btn.pack(anchor="w", padx=SPACE_LG, pady=(SPACE_SM, SPACE_XS))
        else:
            notes_box.insert("1.0", "(Klik tombol di bawah untuk aktifkan catatan)")
            notes_box.configure(state="disabled")

        # Visual separator before the primary toggle button — sits at the
        # very bottom of the panel per user UX preference.
        sep = ctk.CTkFrame(self.right, fg_color=COLOR_BORDER, height=1)
        sep.pack(fill="x", padx=SPACE_LG, pady=(SPACE_MD, SPACE_SM))

        # Big primary toggle button — replaces the inline AKSI column which
        # users found too small/cramped inside the Treeview.
        if is_coached:
            # Destructive action — cyan outline (secondary/cautious).
            toggle_btn = ctk.CTkButton(
                self.right, text="↶ Batalkan Tandai",
                fg_color="transparent", border_width=1, border_color=COLOR_INFO,
                text_color=COLOR_INFO, hover_color=COLOR_SURFACE_HIGH,
                width=300, height=40,
                font=FONT_BODY_BOLD,
                command=lambda r=row: self._toggle_from_panel(r),
            )
        else:
            # Primary CTA — magenta.
            toggle_btn = ctk.CTkButton(
                self.right, text="✓ Sudah Coaching",
                fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
                text_color=COLOR_BG,
                width=300, height=40,
                font=FONT_BODY_BOLD,
                command=lambda r=row: self._toggle_from_panel(r),
            )
        toggle_btn.pack(anchor="w", padx=SPACE_LG, pady=(0, SPACE_MD))

    def _toggle_from_panel(self, row):
        """Toggle status from the right-panel button. Mirrors _toggle_row."""
        iid = str(row["employee_id"])
        self._toggle_row(iid)

    def _on_save_notes(self, row, text: str):
        start, _end, _num = self._active_range()
        if not start:
            return
        notes_value = text if text else None
        with get_connection(DB_PATH) as conn:
            update_notes(
                conn, employee_id=row["employee_id"], week_start=start,
                notes=notes_value,
            )
        # Refresh: keep selection same row so panel updates
        self._reload()
        iid = str(row["employee_id"])
        if iid in self.tree.get_children():
            self.tree.selection_set(iid)
