from tkinter import messagebox
from tkinter import ttk
import customtkinter as ctk

from src.config import DB_PATH
from src.db.connection import get_connection
from src.db.settings import get_setting
from src.db.attendance import (
    set_reason, list_issues_for_period, count_issues_for_period,
    unresolve_issue,
)
from src.core.insights import resolution_rate
from src.core.session_state import period_state
from src.core.reason_mapper import REASON_LABELS, REASON_NEEDS_DETAIL, render_alasan_ijin
from src.core.week_utils import weeks_in_month, full_month_range
from src.ui.components.kpi_card import KPICard
from src.ui.components.search_bar import SearchBar
from src.ui.components.week_nav import WeekNavBar
from src.ui.theme import (
    FONT_FAMILY,
    COLOR_BG, COLOR_SURFACE, COLOR_SURFACE_HIGH,
    COLOR_BORDER,
    COLOR_ACCENT, COLOR_ACCENT_HOVER,
    COLOR_INFO, COLOR_SUCCESS, COLOR_WARN,
    COLOR_TEXT, COLOR_TEXT_MUTED,
    COLOR_ROW_TINT_OPEN, COLOR_ROW_TINT_RESOLVED,
    FONT_DISPLAY,
    FONT_BODY, FONT_BODY_BOLD, FONT_SMALL, FONT_LABEL,
    SPACE_XS, SPACE_MD, SPACE_LG,
    RADIUS_MD,
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
        self._search_query = ""

        self._setup_treeview_style()
        self._build_header()
        self._build_stats()
        self._build_tables_and_panel()
        self._reload()

        # Search shortcuts (Ctrl+F focus + click-outside blur) live in the
        # SearchBar component so the corrected focus logic is shared, not
        # copy-pasted across screens.
        self._search.install_shortcuts(self)

    def _setup_treeview_style(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        # OPEN table — subtle rose-tinted row bg (via tag, see _reload).
        style.configure(
            "Open.Treeview",
            background=COLOR_SURFACE, fieldbackground=COLOR_SURFACE,
            foreground=COLOR_TEXT, rowheight=24, borderwidth=0,
            font=FONT_SMALL,
        )
        style.configure(
            "Open.Treeview.Heading",
            background=COLOR_SURFACE_HIGH, foreground=COLOR_TEXT_MUTED,
            relief="flat", font=(FONT_FAMILY, 9, "bold"),
        )
        # Phase 4a: drop lavender selection workaround (was commit 3af2277).
        # New semantic palette makes COLOR_SURFACE_HIGH a clean neutral hover
        # that doesn't conflict with any row tag or status color.
        style.map(
            "Open.Treeview",
            background=[("selected", COLOR_SURFACE_HIGH)],
            foreground=[("selected", COLOR_TEXT)],
        )
        # RESOLVED table — subtle emerald-tinted row bg (via tag, see _reload).
        style.configure(
            "Resolved.Treeview",
            background=COLOR_SURFACE, fieldbackground=COLOR_SURFACE,
            foreground=COLOR_TEXT, rowheight=24, borderwidth=0,
            font=FONT_SMALL,
        )
        style.configure(
            "Resolved.Treeview.Heading",
            background=COLOR_SURFACE_HIGH, foreground=COLOR_TEXT_MUTED,
            relief="flat", font=(FONT_FAMILY, 9, "bold"),
        )
        style.map(
            "Resolved.Treeview",
            background=[("selected", COLOR_SURFACE_HIGH)],
            foreground=[("selected", COLOR_TEXT)],
        )

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, SPACE_MD))
        ctk.CTkLabel(header, text="Issues",
                     font=FONT_DISPLAY,
                     text_color=COLOR_TEXT).pack(side="left", padx=(0, SPACE_LG))
        self.nav = WeekNavBar(
            header, current_month=self._current_month,
            on_change=self._on_period_change, initial=period_state.get(),
        )
        self.nav.pack(side="left")
        ctk.CTkButton(
            header, text="+ Resolve Massal", command=self._on_batch_resolve,
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
            text_color=COLOR_BG, font=FONT_BODY_BOLD, width=160,
        ).pack(side="right")

    def _on_period_change(self, _key):
        period_state.set(_key)
        self._reload()

    def _on_batch_resolve(self):
        from src.ui.components.batch_resolve_dialog import BatchResolveDialog
        start, end = self._active_range()
        BatchResolveDialog(
            self.winfo_toplevel(),
            period_start=start, period_end=end,
            on_done=self._reload,
        )

    def _build_stats(self):
        self.stats = ctk.CTkFrame(self, fg_color="transparent")
        self.stats.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, SPACE_MD))
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
        # Conditional rate color: emerald if > 75%, rose otherwise. When
        # no data exists (total = 0) keep the neutral muted look.
        if rr["total"] > 0:
            rate_color = COLOR_SUCCESS if rr["rate_pct"] > 75 else COLOR_WARN
        else:
            rate_color = COLOR_TEXT_MUTED

        # Semantic colors per JTS palette:
        #   Open    → rose (warn) — needs attention
        #   Resolved→ emerald (success)
        #   NA      → cyan (info) — neutral, "no shift"
        #   Total   → white (neutral)
        #   Rate %  → conditional emerald/rose
        cards = [
            ("Open", str(counts["open"]), COLOR_WARN),
            ("Resolved", str(counts["resolved"]), COLOR_SUCCESS),
            ("NA", str(counts["na"]), COLOR_INFO),
            ("Total", str(counts["total"]), COLOR_TEXT),
            ("Resolution Rate", rate_str, rate_color),
        ]
        for i, (label, val, color) in enumerate(cards):
            c = KPICard(self.stats, label, val, value_color=color)
            c.grid(row=0, column=i, padx=SPACE_XS, sticky="ew")
            self._stats_cards.append(c)

    def _build_tables_and_panel(self):
        left = ctk.CTkFrame(self, fg_color="transparent")
        left.grid(row=2, column=0, sticky="nsew", padx=(0, SPACE_MD))
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(1, weight=2)
        left.grid_rowconfigure(3, weight=1)

        # Row 0: filter row — "OPEN ISSUES" label on the left, SearchBar on the right.
        # The SearchBar filters BOTH Open and Resolved treeviews; placing it
        # inline with the OPEN ISSUES label visually anchors it to the table
        # content it filters and avoids competing with header widgets.
        filter_row = ctk.CTkFrame(left, fg_color="transparent")
        filter_row.grid(row=0, column=0, sticky="ew", pady=(0, SPACE_XS))
        filter_row.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            filter_row, text="OPEN ISSUES",
            font=FONT_LABEL, text_color=COLOR_WARN,
        ).grid(row=0, column=0, sticky="w")
        self._search = SearchBar(
            filter_row, on_change=self._apply_filter, width=240,
        )
        self._search.grid(row=0, column=1, sticky="e")
        self.open_tree = self._make_tree(left, style_name="Open.Treeview", show_reason=False)
        self.open_tree.grid(row=1, column=0, sticky="nsew")
        # Subtle rose tint on OPEN rows for stronger differentiation
        # (very low-saturation so it doesn't fight with selection highlight).
        self.open_tree.tag_configure("open_row", background=COLOR_ROW_TINT_OPEN)
        self.open_tree.bind("<<TreeviewSelect>>", self._on_select_open)
        self.open_tree.bind("<Return>", self._on_select_open)

        ctk.CTkLabel(left, text="RESOLVED",
                     font=FONT_LABEL,
                     text_color=COLOR_SUCCESS
                     ).grid(row=2, column=0, sticky="w", pady=(SPACE_MD, SPACE_XS))
        self.resolved_tree = self._make_tree(left, style_name="Resolved.Treeview", show_reason=True)
        self.resolved_tree.grid(row=3, column=0, sticky="nsew")
        self.resolved_tree.tag_configure("resolved_row", background=COLOR_ROW_TINT_RESOLVED)
        self.resolved_tree.bind("<<TreeviewSelect>>", self._on_select_resolved)
        self.resolved_tree.bind("<Return>", self._on_select_resolved)

        right = ctk.CTkFrame(
            self, fg_color=COLOR_SURFACE,
            border_width=1, border_color=COLOR_BORDER,
            corner_radius=RADIUS_MD,
        )
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
                     font=FONT_BODY, text_color=COLOR_TEXT_MUTED
                     ).pack(pady=80, padx=SPACE_LG)

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
                     font=FONT_BODY, text_color=COLOR_TEXT
                     ).pack(anchor="w", padx=SPACE_LG, pady=(SPACE_LG, SPACE_MD))

        ctk.CTkLabel(self.right, text="Kategori alasan:",
                     font=FONT_SMALL, text_color=COLOR_TEXT_MUTED
                     ).pack(anchor="w", padx=SPACE_LG)

        labels = list(REASON_LABELS.values())
        self._label_to_key = {v: k for k, v in REASON_LABELS.items()}
        current = row_data.get("reason_category")
        current_label = REASON_LABELS.get(current, "") if current else ""

        self.cat_var = ctk.StringVar(value=current_label)
        self.cat_combo = ctk.CTkComboBox(
            self.right, values=labels, variable=self.cat_var,
            width=300, command=self._on_cat_change,
            fg_color=COLOR_SURFACE_HIGH, button_color=COLOR_ACCENT,
            button_hover_color=COLOR_ACCENT_HOVER,
            border_color=COLOR_BORDER, text_color=COLOR_TEXT,
            font=FONT_BODY,
        )
        self.cat_combo.pack(anchor="w", padx=SPACE_LG, pady=(SPACE_XS, SPACE_MD))
        # Bind Enter directly on the combobox AND its inner entry — Tk's
        # per-widget bind only fires when THAT widget has focus, and
        # CTkComboBox routes typing through an inner ._entry that owns
        # the actual focus when the user types into the field.
        self.cat_combo.bind(
            "<Return>", lambda _e: (self._on_save(), "break")[1])
        if hasattr(self.cat_combo, "_entry"):
            self.cat_combo._entry.bind(
                "<Return>", lambda _e: (self._on_save(), "break")[1])

        # Pre-create detail widgets (hidden by default; shown in _on_cat_change)
        self.detail_label = ctk.CTkLabel(self.right, text="Detail:",
                                          font=FONT_SMALL,
                                          text_color=COLOR_TEXT_MUTED)
        self.detail_entry = ctk.CTkEntry(
            self.right, width=300,
            fg_color=COLOR_SURFACE_HIGH, border_width=1,
            border_color=COLOR_BORDER, text_color=COLOR_TEXT,
            font=FONT_BODY,
        )
        # Enter on the detail entry submits Save (same rationale as combo).
        self.detail_entry.bind(
            "<Return>", lambda _e: (self._on_save(), "break")[1])
        if row_data.get("reason_detail"):
            self.detail_entry.insert(0, row_data["reason_detail"])

        # Save button — magenta primary CTA per JTS palette.
        self.save_btn = ctk.CTkButton(
            self.right, text="Simpan", command=self._on_save,
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
            text_color=COLOR_BG, width=300, font=FONT_BODY_BOLD,
        )

        # Unresolve button — only shown when row is currently resolved
        # (reason_category is not None). Anchored to the BOTTOM of the panel
        # (well separated from Save) to reduce accidental clicks on a
        # destructive action. Cyan outline = "secondary/cautious" semantic.
        self.unresolve_btn = ctk.CTkButton(
            self.right, text="↶ Batalkan Resolve", command=self._on_unresolve,
            fg_color="transparent", border_width=1, border_color=COLOR_INFO,
            text_color=COLOR_INFO, hover_color=COLOR_SURFACE_HIGH,
            width=300, font=FONT_BODY_BOLD,
        )
        # Thin separator above the unresolve button for visual grouping.
        self.unresolve_sep = ctk.CTkFrame(
            self.right, fg_color=COLOR_BORDER, height=1,
        )
        self._row_is_resolved = current is not None

        # Initial layout (Save below the optional detail)
        self._lay_out_form(initial_cat=current)
        # Enter submits the form when focus is on the right panel.
        self.right.bind("<Return>", lambda _e: (self._on_save(), "break")[1])

    def _lay_out_form(self, initial_cat: str | None):
        """(Re)pack detail widgets and Save button at top of panel; unresolve
        button + separator pinned to the bottom (only if row is resolved).

        Top→bottom flow:
            cat_combo → (detail_label → detail_entry)? → save_btn
            ...empty space...
            unresolve_sep → unresolve_btn  (only if resolved)
        """
        self.detail_label.pack_forget()
        self.detail_entry.pack_forget()
        self.save_btn.pack_forget()
        self.unresolve_btn.pack_forget()
        self.unresolve_sep.pack_forget()

        if initial_cat and initial_cat in REASON_NEEDS_DETAIL:
            self.detail_label.pack(anchor="w", padx=SPACE_LG)
            self.detail_entry.pack(anchor="w", padx=SPACE_LG, pady=(SPACE_XS, SPACE_MD))
        self.save_btn.pack(anchor="w", padx=SPACE_LG, pady=(SPACE_MD, SPACE_XS))

        if self._row_is_resolved:
            # Pack unresolve button FIRST with side="bottom" so it lands at
            # the very bottom; then the separator above it.
            self.unresolve_btn.pack(side="bottom", anchor="w",
                                     padx=SPACE_LG, pady=(0, SPACE_MD))
            self.unresolve_sep.pack(side="bottom", fill="x",
                                     padx=SPACE_LG, pady=(SPACE_MD, SPACE_XS))

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

    def _on_unresolve(self):
        if self.selected_id is None:
            return
        confirmed = messagebox.askyesno(
            "Konfirmasi",
            "Batalkan resolve?\n\n"
            "Kategori dan detail alasan akan dihapus.\n"
            "Issue akan kembali ke status Open.",
        )
        if not confirmed:
            return
        with get_connection(DB_PATH) as conn:
            unresolve_issue(conn, attendance_id=self.selected_id)
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

    def _render_rows(self, query: str):
        """Re-render Open + Resolved treeviews from self._row_cache,
        filtering by employee name (case-insensitive substring)."""
        q = query.lower().strip()
        for tv in (self.open_tree, self.resolved_tree):
            for iid in tv.get_children():
                tv.delete(iid)
        visible_open = visible_resolved = total_open = total_resolved = 0
        for row in self._row_cache.values():
            is_resolved = row["reason_category"] is not None
            if is_resolved:
                total_resolved += 1
            else:
                total_open += 1
            if q and q not in row["nama"].lower():
                continue
            if is_resolved:
                try:
                    alasan = render_alasan_ijin(row["reason_category"], row["reason_detail"])
                except Exception:
                    alasan = row["reason_category"] or "-"
                self.resolved_tree.insert(
                    "", "end", iid=str(row["id"]),
                    values=(row["nama"], row["dept"] or "-", row["tanggal"],
                            row["hari"] or "-", row["masuk"] or "—",
                            row["keluar"] or "—", alasan),
                    tags=("resolved_row",),
                )
                visible_resolved += 1
            else:
                self.open_tree.insert(
                    "", "end", iid=str(row["id"]),
                    values=(row["nama"], row["dept"] or "-", row["tanggal"],
                            row["hari"] or "-", row["masuk"] or "—",
                            row["keluar"] or "—"),
                    tags=("open_row",),
                )
                visible_open += 1
        self._search.set_count(visible_open + visible_resolved, total_open + total_resolved)

    def _apply_filter(self, query: str):
        self._search_query = query
        self._render_rows(query)

    def _reload(self):
        start, end = self._active_range()
        self._row_cache = {}

        with get_connection(DB_PATH) as conn:
            counts = count_issues_for_period(conn, start, end)
            open_rows = list_issues_for_period(conn, start, end, resolved=False)
            resolved_rows = list_issues_for_period(conn, start, end, resolved=True)

        self._render_stats(counts)

        for r in open_rows:
            d = dict(r)
            self._row_cache[d["id"]] = d

        for r in resolved_rows:
            d = dict(r)
            self._row_cache[d["id"]] = d

        self._render_rows(self._search_query)
