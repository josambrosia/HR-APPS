from tkinter import messagebox
from tkinter import ttk
import customtkinter as ctk

from src.config import DB_PATH
from src.db.connection import get_connection
from src.db.settings import get_setting
from src.db.attendance import (
    set_reason, list_issues_for_period, count_issues_for_period,
)
from src.core.reason_mapper import REASON_LABELS, REASON_NEEDS_DETAIL
from src.core.week_utils import weeks_in_month, full_month_range
from src.ui.components.kpi_card import KPICard
from src.ui.theme import FONT_FAMILY, COLOR_OK, COLOR_WARN, COLOR_ERR, COLOR_PANEL


class IssuesScreen(ctk.CTkFrame):
    """Issues screen — per-week view with stats, sorted by nama+tanggal,
    open/resolved separated, ttk.Treeview for speed."""

    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self.grid_columnconfigure(0, weight=2)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=1)  # tables row

        # Cache current_month
        with get_connection(DB_PATH) as conn:
            self._current_month = get_setting(conn, "current_month") or ""

        self.selected_id = None
        self.active_period = "semua"  # "semua" | "minggu_N"
        self._setup_treeview_style()
        self._build_navbar()
        self._build_stats()
        self._build_tables_and_panel()
        self._reload()

    # ------------------------------------------------------------- Styling

    def _setup_treeview_style(self):
        """Apply dark theme to ttk.Treeview to match customtkinter."""
        style = ttk.Style()
        # Ensure we are using a theme that respects our overrides
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure(
            "Dark.Treeview",
            background=COLOR_PANEL,
            foreground="#e5e5e5",
            fieldbackground=COLOR_PANEL,
            rowheight=26,
            borderwidth=0,
        )
        style.configure(
            "Dark.Treeview.Heading",
            background="#0f172a",
            foreground="#94a3b8",
            relief="flat",
            font=(FONT_FAMILY, 10, "bold"),
        )
        style.map(
            "Dark.Treeview",
            background=[("selected", "#3b82f6")],
            foreground=[("selected", "white")],
        )

    # --------------------------------------------------------------- Nav

    def _build_navbar(self):
        nav = ctk.CTkFrame(self, fg_color="transparent")
        nav.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))

        ctk.CTkLabel(nav, text="Issues", font=(FONT_FAMILY, 24, "bold")
                     ).pack(side="left", padx=(0, 16))

        # Build tabs: Semua + Minggu 1..N
        self._nav_buttons = {}
        self._make_nav_btn(nav, "semua", "Semua")
        if self._current_month:
            for num, start, end in weeks_in_month(self._current_month):
                s_day = start.split("-")[2]
                e_day = end.split("-")[2]
                key = f"minggu_{num}"
                label = f"Minggu {num} ({s_day}-{e_day})"
                self._make_nav_btn(nav, key, label)

        self._highlight_active()

    def _make_nav_btn(self, parent, key, label):
        btn = ctk.CTkButton(
            parent, text=label,
            command=lambda k=key: self._on_nav_click(k),
            fg_color="transparent", hover_color="#334155",
            corner_radius=6, height=32, width=120,
        )
        btn.pack(side="left", padx=4)
        self._nav_buttons[key] = btn

    def _highlight_active(self):
        for key, btn in self._nav_buttons.items():
            if key == self.active_period:
                btn.configure(fg_color="#3b82f6", text_color="white")
            else:
                btn.configure(fg_color="transparent", text_color="#e5e5e5")

    def _on_nav_click(self, key):
        self.active_period = key
        self._highlight_active()
        self._reload()

    # ----------------------------------------------------------- Stats

    def _build_stats(self):
        self.stats = ctk.CTkFrame(self, fg_color="transparent")
        self.stats.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        for i in range(4):
            self.stats.grid_columnconfigure(i, weight=1)
        # KPICards inserted in _reload after counts are computed
        self._stats_cards = []

    def _render_stats(self, counts):
        for c in self._stats_cards:
            c.destroy()
        self._stats_cards = []
        c1 = KPICard(self.stats, "Open", str(counts["open"]),
                     value_color=COLOR_WARN)
        c1.grid(row=0, column=0, padx=4, sticky="ew")
        c2 = KPICard(self.stats, "Resolved", str(counts["resolved"]),
                     value_color=COLOR_OK)
        c2.grid(row=0, column=1, padx=4, sticky="ew")
        c3 = KPICard(self.stats, "NA", str(counts["na"]),
                     value_color=COLOR_ERR)
        c3.grid(row=0, column=2, padx=4, sticky="ew")
        c4 = KPICard(self.stats, "Total", str(counts["total"]))
        c4.grid(row=0, column=3, padx=4, sticky="ew")
        self._stats_cards = [c1, c2, c3, c4]

    # -------------------------------------------------- Tables + Panel

    def _build_tables_and_panel(self):
        # Left side: open + resolved tables stacked
        left = ctk.CTkFrame(self, fg_color="transparent")
        left.grid(row=2, column=0, sticky="nsew", padx=(0, 12))
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(1, weight=2)
        left.grid_rowconfigure(3, weight=1)

        ctk.CTkLabel(left, text="OPEN ISSUES",
                     font=(FONT_FAMILY, 11, "bold"), text_color="#94a3b8"
                     ).grid(row=0, column=0, sticky="w", pady=(0, 4))
        self.open_tree = self._make_tree(left)
        self.open_tree.grid(row=1, column=0, sticky="nsew")
        self.open_tree.bind("<<TreeviewSelect>>", self._on_select_open)

        ctk.CTkLabel(left, text="RESOLVED",
                     font=(FONT_FAMILY, 11, "bold"), text_color="#94a3b8"
                     ).grid(row=2, column=0, sticky="w", pady=(12, 4))
        self.resolved_tree = self._make_tree(left, show_reason=True)
        self.resolved_tree.grid(row=3, column=0, sticky="nsew")
        self.resolved_tree.bind("<<TreeviewSelect>>", self._on_select_resolved)

        # Right side: reason input panel
        right = ctk.CTkFrame(self, fg_color=COLOR_PANEL, corner_radius=8)
        right.grid(row=2, column=1, sticky="nsew")
        self.right = right
        self._build_panel_empty()

    def _make_tree(self, parent, show_reason: bool = False):
        cols = ["nama", "dept", "tanggal", "hari", "masuk", "keluar"]
        if show_reason:
            cols.append("alasan")
        tree = ttk.Treeview(
            parent, columns=cols, show="headings",
            style="Dark.Treeview", height=8, selectmode="browse",
        )
        widths = {"nama": 130, "dept": 100, "tanggal": 90, "hari": 70,
                  "masuk": 60, "keluar": 60, "alasan": 200}
        labels = {"nama": "Nama", "dept": "Dept", "tanggal": "Tanggal",
                  "hari": "Hari", "masuk": "Masuk", "keluar": "Keluar",
                  "alasan": "Alasan"}
        for c in cols:
            tree.heading(c, text=labels[c])
            tree.column(c, width=widths[c], anchor="w")
        return tree

    # --------------------------------------------------- Reason Panel

    def _build_panel_empty(self):
        for w in self.right.winfo_children():
            w.destroy()
        ctk.CTkLabel(self.right,
                     text="Pilih issue di kiri untuk input alasan",
                     font=(FONT_FAMILY, 12), text_color="#94a3b8"
                     ).pack(pady=80, padx=16)

    def _build_panel_for(self, row_data):
        for w in self.right.winfo_children():
            w.destroy()
        info = (
            f"{row_data['nama']} ({row_data['dept'] or '-'})\n"
            f"{row_data['hari'] or '-'}, {row_data['tanggal']}\n"
            f"Masuk: {row_data['masuk'] or '—'}   "
            f"Keluar: {row_data['keluar'] or '—'}"
        )
        ctk.CTkLabel(self.right, text=info, justify="left",
                     font=(FONT_FAMILY, 12)
                     ).pack(anchor="w", padx=16, pady=(16, 12))

        ctk.CTkLabel(self.right, text="Kategori alasan:",
                     font=(FONT_FAMILY, 11)).pack(anchor="w", padx=16)

        # Show only human label in dropdown; keep mapping label→key
        labels = list(REASON_LABELS.values())
        self._label_to_key = {v: k for k, v in REASON_LABELS.items()}
        # Preselect current category if any
        current = row_data.get("reason_category")
        current_label = REASON_LABELS.get(current, "") if current else ""

        self.cat_var = ctk.StringVar(value=current_label)
        self.cat_combo = ctk.CTkComboBox(
            self.right, values=labels, variable=self.cat_var,
            width=300, command=self._on_cat_change,
        )
        self.cat_combo.pack(anchor="w", padx=16, pady=(4, 12))

        self.detail_label = ctk.CTkLabel(self.right, text="Detail:",
                                          font=(FONT_FAMILY, 11))
        self.detail_entry = ctk.CTkEntry(self.right, width=300)
        if row_data.get("reason_detail"):
            self.detail_entry.insert(0, row_data["reason_detail"])
        # Conditionally show
        if current and current in REASON_NEEDS_DETAIL:
            self.detail_label.pack(anchor="w", padx=16)
            self.detail_entry.pack(anchor="w", padx=16, pady=(4, 12))

        ctk.CTkButton(self.right, text="Simpan",
                      command=self._on_save, fg_color=COLOR_OK,
                      text_color="#0a0a0a", width=300
                      ).pack(anchor="w", padx=16, pady=12)

    def _on_cat_change(self, _):
        label = self.cat_var.get()
        key = self._label_to_key.get(label, "")
        if key in REASON_NEEDS_DETAIL:
            self.detail_label.pack(anchor="w", padx=16)
            self.detail_entry.pack(anchor="w", padx=16, pady=(4, 12))
        else:
            self.detail_label.pack_forget()
            self.detail_entry.pack_forget()

    def _on_save(self):
        if self.selected_id is None:
            return
        label = self.cat_var.get()
        cat = self._label_to_key.get(label, "")
        if cat not in REASON_LABELS:
            messagebox.showwarning(
                "Pilih kategori", "Belum memilih kategori alasan.")
            return
        detail = (self.detail_entry.get().strip()
                  if cat in REASON_NEEDS_DETAIL else None) or None
        with get_connection(DB_PATH) as conn:
            set_reason(conn, attendance_id=self.selected_id,
                       category=cat, detail=detail)
        self._reload()
        self._build_panel_empty()
        self.selected_id = None

    # ------------------------------------------------------- Selection

    def _on_select_open(self, _evt):
        sel = self.open_tree.selection()
        if not sel:
            return
        # Clear selection in resolved tree to avoid confusion
        self.resolved_tree.selection_remove(self.resolved_tree.selection())
        att_id = int(sel[0])
        self.selected_id = att_id
        row_data = self._row_cache.get(att_id)
        if row_data:
            self._build_panel_for(row_data)

    def _on_select_resolved(self, _evt):
        sel = self.resolved_tree.selection()
        if not sel:
            return
        self.open_tree.selection_remove(self.open_tree.selection())
        att_id = int(sel[0])
        self.selected_id = att_id
        row_data = self._row_cache.get(att_id)
        if row_data:
            self._build_panel_for(row_data)

    # ------------------------------------------------------- Range

    def _active_range(self):
        """Resolve (start, end) for the active period."""
        if not self._current_month:
            # Defensive fallback — no data anyway
            return "1970-01-01", "9999-12-31"
        if self.active_period == "semua":
            return full_month_range(self._current_month)
        # minggu_N
        try:
            num = int(self.active_period.split("_")[1])
        except (IndexError, ValueError):
            return full_month_range(self._current_month)
        for n, start, end in weeks_in_month(self._current_month):
            if n == num:
                return start, end
        return full_month_range(self._current_month)

    # ------------------------------------------------------- Reload

    def _reload(self):
        start, end = self._active_range()
        self._row_cache = {}

        # Clear treeviews
        for item in self.open_tree.get_children():
            self.open_tree.delete(item)
        for item in self.resolved_tree.get_children():
            self.resolved_tree.delete(item)

        # Counts for the active range
        with get_connection(DB_PATH) as conn:
            counts = count_issues_for_period(conn, start, end)
            open_rows = list_issues_for_period(conn, start, end, resolved=False)
            resolved_rows = list_issues_for_period(conn, start, end, resolved=True)

        self._render_stats(counts)

        # Populate open
        for r in open_rows:
            d = dict(r)
            self._row_cache[d["id"]] = d
            self.open_tree.insert(
                "", "end", iid=str(d["id"]),
                values=(d["nama"], d["dept"] or "-", d["tanggal"],
                        d["hari"] or "-", d["masuk"] or "—",
                        d["keluar"] or "—"),
            )

        # Populate resolved (with alasan column)
        from src.core.reason_mapper import render_alasan_ijin
        for r in resolved_rows:
            d = dict(r)
            self._row_cache[d["id"]] = d
            try:
                alasan = render_alasan_ijin(d["reason_category"], d["reason_detail"])
            except Exception:
                alasan = d["reason_category"] or "-"
            self.resolved_tree.insert(
                "", "end", iid=str(d["id"]),
                values=(d["nama"], d["dept"] or "-", d["tanggal"],
                        d["hari"] or "-", d["masuk"] or "—",
                        d["keluar"] or "—", alasan),
            )
