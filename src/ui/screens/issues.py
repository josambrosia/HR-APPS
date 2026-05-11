from tkinter import messagebox
from tkinter import ttk
import customtkinter as ctk

from src.config import DB_PATH
from src.db.connection import get_connection
from src.db.settings import get_setting
from src.db.attendance import (
    set_reason, list_issues_for_period, count_issues_for_period,
)
from src.core.insights import resolution_rate
from src.core.reason_mapper import REASON_LABELS, REASON_NEEDS_DETAIL, render_alasan_ijin
from src.core.week_utils import weeks_in_month, full_month_range
from src.ui.components.kpi_card import KPICard
from src.ui.components.week_nav import WeekNavBar
from src.ui.theme import (
    FONT_FAMILY, COLOR_OK, COLOR_WARN, COLOR_ERR, COLOR_ACCENT,
    COLOR_PANEL, COLOR_PANEL_OPEN, COLOR_PANEL_RESOLVED,
    COLOR_TEXT, COLOR_TEXT_DIM,
)


class IssuesScreen(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self.grid_columnconfigure(0, weight=2)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=1)

        with get_connection(DB_PATH) as conn:
            self._current_month = get_setting(conn, "current_month") or ""

        self.selected_id = None
        self._row_cache = {}

        self._setup_treeview_style()
        self._build_header()
        self._build_stats()
        self._build_tables_and_panel()
        self._reload()

    def _setup_treeview_style(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        # Open table — subtly warmer panel
        style.configure(
            "Open.Treeview",
            background=COLOR_PANEL_OPEN, fieldbackground=COLOR_PANEL_OPEN,
            foreground=COLOR_TEXT, rowheight=26, borderwidth=0,
        )
        style.configure(
            "Open.Treeview.Heading",
            background="#2C1B47", foreground=COLOR_TEXT_DIM,
            relief="flat", font=(FONT_FAMILY, 10, "bold"),
        )
        style.map(
            "Open.Treeview",
            background=[("selected", COLOR_ACCENT)],
            foreground=[("selected", "#1E104E")],
        )
        # Resolved table — subtly cooler/darker panel
        style.configure(
            "Resolved.Treeview",
            background=COLOR_PANEL_RESOLVED, fieldbackground=COLOR_PANEL_RESOLVED,
            foreground=COLOR_TEXT, rowheight=26, borderwidth=0,
        )
        style.configure(
            "Resolved.Treeview.Heading",
            background="#2C1B47", foreground=COLOR_TEXT_DIM,
            relief="flat", font=(FONT_FAMILY, 10, "bold"),
        )
        style.map(
            "Resolved.Treeview",
            background=[("selected", COLOR_OK)],
            foreground=[("selected", "#1E104E")],
        )

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        ctk.CTkLabel(header, text="Issues",
                     font=(FONT_FAMILY, 24, "bold"),
                     text_color=COLOR_TEXT).pack(side="left", padx=(0, 16))
        self.nav = WeekNavBar(
            header, current_month=self._current_month,
            on_change=self._on_period_change, initial="semua",
        )
        self.nav.pack(side="left")

    def _on_period_change(self, _key):
        self._reload()

    def _build_stats(self):
        self.stats = ctk.CTkFrame(self, fg_color="transparent")
        self.stats.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        for i in range(5):
            self.stats.grid_columnconfigure(i, weight=1)
        self._stats_cards = []

    def _render_stats(self, counts):
        for c in self._stats_cards:
            c.destroy()
        self._stats_cards = []

        # Compute resolution rate for the current range
        start, end = self._active_range()
        with get_connection(DB_PATH) as conn:
            rr = resolution_rate(conn, start, end)
        rate_str = f"{rr['rate_pct']}%" if rr["total"] > 0 else "—"

        cards = [
            ("Open", str(counts["open"]), COLOR_ACCENT),
            ("Resolved", str(counts["resolved"]), COLOR_OK),
            ("NA", str(counts["na"]), COLOR_ERR),
            ("Total", str(counts["total"]), COLOR_TEXT),
            ("Resolution Rate", rate_str, COLOR_OK),
        ]
        for i, (label, val, color) in enumerate(cards):
            c = KPICard(self.stats, label, val, value_color=color)
            c.grid(row=0, column=i, padx=4, sticky="ew")
            self._stats_cards.append(c)

    def _build_tables_and_panel(self):
        left = ctk.CTkFrame(self, fg_color="transparent")
        left.grid(row=2, column=0, sticky="nsew", padx=(0, 12))
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(1, weight=2)
        left.grid_rowconfigure(3, weight=1)

        ctk.CTkLabel(left, text="OPEN ISSUES",
                     font=(FONT_FAMILY, 11, "bold"),
                     text_color=COLOR_ACCENT
                     ).grid(row=0, column=0, sticky="w", pady=(0, 4))
        self.open_tree = self._make_tree(left, style_name="Open.Treeview", show_reason=False)
        self.open_tree.grid(row=1, column=0, sticky="nsew")
        self.open_tree.bind("<<TreeviewSelect>>", self._on_select_open)
        self.open_tree.bind("<Return>", self._on_select_open)

        ctk.CTkLabel(left, text="RESOLVED",
                     font=(FONT_FAMILY, 11, "bold"),
                     text_color=COLOR_OK
                     ).grid(row=2, column=0, sticky="w", pady=(12, 4))
        self.resolved_tree = self._make_tree(left, style_name="Resolved.Treeview", show_reason=True)
        self.resolved_tree.grid(row=3, column=0, sticky="nsew")
        self.resolved_tree.bind("<<TreeviewSelect>>", self._on_select_resolved)
        self.resolved_tree.bind("<Return>", self._on_select_resolved)

        right = ctk.CTkFrame(self, fg_color=COLOR_PANEL, corner_radius=8)
        right.grid(row=2, column=1, sticky="nsew")
        self.right = right
        self._build_panel_empty()

    def _make_tree(self, parent, *, style_name: str, show_reason: bool):
        cols = ["nama", "dept", "tanggal", "hari", "masuk", "keluar"]
        if show_reason:
            cols.append("alasan")
        tree = ttk.Treeview(
            parent, columns=cols, show="headings",
            style=style_name, height=8, selectmode="browse",
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

    def _build_panel_empty(self):
        for w in self.right.winfo_children():
            w.destroy()
        ctk.CTkLabel(self.right,
                     text="Pilih issue di kiri untuk input alasan",
                     font=(FONT_FAMILY, 12), text_color=COLOR_TEXT_DIM
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
                     font=(FONT_FAMILY, 12), text_color=COLOR_TEXT
                     ).pack(anchor="w", padx=16, pady=(16, 12))

        ctk.CTkLabel(self.right, text="Kategori alasan:",
                     font=(FONT_FAMILY, 11), text_color=COLOR_TEXT_DIM
                     ).pack(anchor="w", padx=16)

        labels = list(REASON_LABELS.values())
        self._label_to_key = {v: k for k, v in REASON_LABELS.items()}
        current = row_data.get("reason_category")
        current_label = REASON_LABELS.get(current, "") if current else ""

        self.cat_var = ctk.StringVar(value=current_label)
        self.cat_combo = ctk.CTkComboBox(
            self.right, values=labels, variable=self.cat_var,
            width=300, command=self._on_cat_change,
        )
        self.cat_combo.pack(anchor="w", padx=16, pady=(4, 12))

        # Pre-create detail widgets (hidden by default; shown in _on_cat_change)
        self.detail_label = ctk.CTkLabel(self.right, text="Detail:",
                                          font=(FONT_FAMILY, 11),
                                          text_color=COLOR_TEXT_DIM)
        self.detail_entry = ctk.CTkEntry(self.right, width=300)
        if row_data.get("reason_detail"):
            self.detail_entry.insert(0, row_data["reason_detail"])

        # Save button — keep a reference so we can repack it below detail when shown
        self.save_btn = ctk.CTkButton(
            self.right, text="Simpan", command=self._on_save,
            fg_color=COLOR_OK, text_color="#1E104E", width=300,
        )

        # Initial layout (Save below the optional detail)
        self._lay_out_form(initial_cat=current)

    def _lay_out_form(self, initial_cat: str | None):
        """(Re)pack detail widgets and Save button in correct order.

        Order:  cat_combo  ->  (detail_label  ->  detail_entry)?  ->  save_btn
        """
        # Always re-pack from the bottom so Save lands last
        self.detail_label.pack_forget()
        self.detail_entry.pack_forget()
        self.save_btn.pack_forget()

        if initial_cat and initial_cat in REASON_NEEDS_DETAIL:
            self.detail_label.pack(anchor="w", padx=16)
            self.detail_entry.pack(anchor="w", padx=16, pady=(4, 12))
        self.save_btn.pack(anchor="w", padx=16, pady=12)

    def _on_cat_change(self, _):
        label = self.cat_var.get()
        key = self._label_to_key.get(label, "")
        self._lay_out_form(initial_cat=key)

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

    def _on_select_open(self, _evt):
        sel = self.open_tree.selection()
        if not sel:
            return
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

    def _active_range(self):
        if not self._current_month:
            return "1970-01-01", "9999-12-31"
        if self.nav.active == "semua":
            return full_month_range(self._current_month)
        try:
            num = int(self.nav.active.split("_")[1])
        except (IndexError, ValueError):
            return full_month_range(self._current_month)
        for n, start, end in weeks_in_month(self._current_month):
            if n == num:
                return start, end
        return full_month_range(self._current_month)

    def _reload(self):
        start, end = self._active_range()
        self._row_cache = {}

        for item in self.open_tree.get_children():
            self.open_tree.delete(item)
        for item in self.resolved_tree.get_children():
            self.resolved_tree.delete(item)

        with get_connection(DB_PATH) as conn:
            counts = count_issues_for_period(conn, start, end)
            open_rows = list_issues_for_period(conn, start, end, resolved=False)
            resolved_rows = list_issues_for_period(conn, start, end, resolved=True)

        self._render_stats(counts)

        for r in open_rows:
            d = dict(r)
            self._row_cache[d["id"]] = d
            self.open_tree.insert(
                "", "end", iid=str(d["id"]),
                values=(d["nama"], d["dept"] or "-", d["tanggal"],
                        d["hari"] or "-", d["masuk"] or "—",
                        d["keluar"] or "—"),
            )

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
