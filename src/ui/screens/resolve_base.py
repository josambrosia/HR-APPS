"""Shared base for the two resolve screens (Issues + Severe Lateness).

Both screens are the same machine: header (title + WeekNavBar +
"+ Resolve Massal" CTA), a 5-card KPI row, Open/Resolved treeviews with
a shared SearchBar filter, and a right-hand resolve panel (kategori +
detail + Simpan / Batalkan Resolve). Until v22 they were ~450-line
copy-paste twins; this base holds ALL the shared structure/behavior and
the subclasses supply only the knobs.

Knobs (class attributes):
    TITLE          — header title text.
    EXTRA_COLUMNS  — (col_id, heading, width, right_aligned) specs
                     appended after the shared nama..keluar columns
                     (before the resolved-only 'alasan'), e.g. the
                     severe screen's "Telat (mnt)" column.

Knobs (hook methods — see each docstring):
    _db_path / _notify_data_changed  — late-bound module globals so tests
                                       keep monkeypatching them on the
                                       SUBCLASS module (established
                                       pattern in all screen tests).
    _load_extra_settings             — extra settings read in __init__.
    _count_rows / _list_rows         — the data-source queries.
    _category_labels                 — reason-category subset.
    _batch_lister_fn                 — open-row lister for BatchResolveDialog.
    _resolution_rate                 — Resolution Rate KPI source.
    _extra_row_values                — cell values for EXTRA_COLUMNS.
    _build_panel_empty               — right-panel empty state.
"""
from tkinter import ttk
import customtkinter as ctk

from src.db.connection import get_connection
from src.db.settings import get_setting
from src.db.attendance import set_reason, unresolve_issue
from src.core.insights import resolution_rate
from src.core.session_state import period_state
from src.core.reason_mapper import REASON_LABELS, REASON_NEEDS_DETAIL, render_alasan_ijin
from src.core.week_utils import resolve_period
from src.ui import feedback
from src.ui.components.kpi_card import KPICard
from src.ui.components.search_bar import SearchBar
from src.ui.components.tree_style import style_treeview, CellTooltip
from src.ui.components.week_nav import WeekNavBar
from src.ui.theme import (
    FONT_FAMILY,
    COLOR_BG, COLOR_SURFACE, COLOR_SURFACE_HIGH,
    COLOR_BORDER,
    COLOR_ACCENT, COLOR_ACCENT_HOVER,
    COLOR_INFO, COLOR_SUCCESS, COLOR_WARN,
    COLOR_TEXT, COLOR_TEXT_MUTED, COLOR_TEXT_DISABLED,
    COLOR_ROW_TINT_OPEN, COLOR_ROW_TINT_RESOLVED,
    FONT_DISPLAY,
    FONT_BODY, FONT_BODY_BOLD, FONT_SMALL, FONT_LABEL,
    SPACE_XS, SPACE_SM, SPACE_MD, SPACE_LG,
    RADIUS_MD,
)

# Debounce for the name filter — rebuilding both treeviews on every
# keystroke is wasteful on large months; 200ms still feels instant but
# coalesces a typing burst into a single re-render.
SEARCH_DEBOUNCE_MS = 200


class ResolveScreenBase(ctk.CTkFrame):
    """Shared structure/behavior of IssuesScreen and SevereLatenessScreen."""

    TITLE: str = ""
    # (col_id, heading, width, right_aligned) — shared leading columns.
    BASE_COLUMNS = (
        ("nama", "Nama", 130, False),
        ("dept", "Dept", 100, False),
        ("tanggal", "Tanggal", 90, False),
        ("hari", "Hari", 70, False),
        ("masuk", "Masuk", 60, True),
        ("keluar", "Keluar", 60, True),
    )
    EXTRA_COLUMNS: tuple = ()
    ALASAN_COLUMN = ("alasan", "Alasan", 260, False)

    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self.grid_columnconfigure(0, weight=2)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=1)

        with get_connection(self._db_path()) as conn:
            self._current_month = get_setting(conn, "current_month") or ""
            self._load_extra_settings(conn)

        self.selected_id = None
        self._row_cache = {}
        self._search_query = ""
        self._last_counts = None

        self._setup_treeview_style()
        self._build_header()
        self._build_stats()
        self._build_tables_and_panel()
        self._reload()

        # Search shortcuts (Ctrl+F focus + click-outside blur) live in the
        # SearchBar component so the corrected focus logic is shared, not
        # copy-pasted across screens.
        self._search.install_shortcuts(self)

    # ------------------------------------------------------------------
    # Hooks — the knobs that differ between Issues and Severe Lateness.

    def _db_path(self):
        """Return the DB path to open. Subclasses return their module-level
        DB_PATH so tests keep monkeypatching `mod.DB_PATH`."""
        raise NotImplementedError

    def _notify_data_changed(self):
        """Bump the cross-screen data version. Subclasses call their
        module-level notify_data_changed so tests keep monkeypatching it."""
        raise NotImplementedError

    def _load_extra_settings(self, conn):
        """Read extra per-screen settings inside the __init__ connection
        (severe: the lateness threshold). Default: nothing."""

    def _count_rows(self, conn, start, end) -> dict:
        """Return {open, resolved, na, total} counts for the period."""
        raise NotImplementedError

    def _list_rows(self, conn, start, end, *, resolved):
        """Return employee-joined rows for the period (resolved True/False)."""
        raise NotImplementedError

    def _category_labels(self) -> list:
        """Reason-category labels offered in the resolve combo."""
        raise NotImplementedError

    def _batch_lister_fn(self):
        """Open-row lister passed to BatchResolveDialog. None = the
        dialog's default open-issues lister (Issues behavior)."""
        return None

    def _resolution_rate(self, counts) -> dict:
        """Return {'total', 'rate_pct'} for the Resolution Rate card.

        Default: the shared insights.resolution_rate helper over the
        active range — the has_issue=1 population, which matches the
        Issues data source. Severe overrides (its set is has_issue=0
        rows, outside the helper's hardcoded predicate).
        """
        start, end = self._active_range()
        with get_connection(self._db_path()) as conn:
            return resolution_rate(conn, start, end)

    def _extra_row_values(self, row) -> tuple:
        """Cell values for EXTRA_COLUMNS, in order. Default: none."""
        return ()

    # ------------------------------------------------------------------
    # Shared structure

    def _setup_treeview_style(self):
        style_treeview("Open.Treeview")
        style_treeview("Resolved.Treeview")

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, SPACE_MD))
        ctk.CTkLabel(header, text=self.TITLE,
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
            lister_fn=self._batch_lister_fn(),
        )

    def _build_stats(self):
        self.stats = ctk.CTkFrame(self, fg_color="transparent")
        self.stats.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, SPACE_MD))
        for i in range(5):
            self.stats.grid_columnconfigure(i, weight=1)

        # Semantic colors per JTS palette:
        #   Open    → rose (warn) — needs attention
        #   Resolved→ emerald (success)
        #   NA      → cyan (info) — neutral, "no shift"
        #   Total   → white (neutral)
        #   Rate %  → conditional emerald/rose (set per render)
        #
        # Cards are built ONCE here; _render_stats only updates the values
        # in place — no destroy+recreate churn on every reload.
        specs = (
            ("Open", COLOR_WARN),
            ("Resolved", COLOR_SUCCESS),
            ("NA", COLOR_INFO),
            ("Total", COLOR_TEXT),
            ("Resolution Rate", COLOR_TEXT_MUTED),
        )
        self._stats_cards = []
        for i, (label, color) in enumerate(specs):
            c = KPICard(self.stats, label, "—", value_color=color)
            c.grid(row=0, column=i, padx=SPACE_XS, sticky="ew")
            self._stats_cards.append(c)

    def _render_stats(self, counts):
        self._last_counts = counts

        rr = self._resolution_rate(counts)
        rate_str = f"{rr['rate_pct']}%" if rr["total"] > 0 else "—"
        # Conditional rate color: emerald if > 75%, rose otherwise. When
        # no data exists (total = 0) keep the neutral muted look.
        if rr["total"] > 0:
            rate_color = COLOR_SUCCESS if rr["rate_pct"] > 75 else COLOR_WARN
        else:
            rate_color = COLOR_TEXT_MUTED

        open_card, resolved_card, na_card, total_card, rate_card = self._stats_cards
        open_card.set_value(str(counts["open"]))
        resolved_card.set_value(str(counts["resolved"]))
        na_card.set_value(str(counts["na"]))
        total_card.set_value(str(counts["total"]))
        rate_card.set_value(rate_str, color=rate_color)

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
            debounce_ms=SEARCH_DEBOUNCE_MS,
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
        CellTooltip(self.resolved_tree, "alasan")

        right = ctk.CTkFrame(
            self, fg_color=COLOR_SURFACE,
            border_width=1, border_color=COLOR_BORDER,
            corner_radius=RADIUS_MD,
        )
        right.grid(row=2, column=1, sticky="nsew")
        self.right = right
        self._build_panel_empty()

    def _make_tree(self, parent, *, style_name: str, show_reason: bool):
        specs = list(self.BASE_COLUMNS) + list(self.EXTRA_COLUMNS)
        if show_reason:
            specs.append(self.ALASAN_COLUMN)
        cols = [s[0] for s in specs]
        tree = ttk.Treeview(
            parent, columns=cols, show="headings",
            style=style_name, height=8, selectmode="browse",
        )
        for col_id, label, width, right_aligned in specs:
            tree.heading(col_id, text=label)
            tree.column(col_id, width=width,
                        anchor="e" if right_aligned else "w")
        return tree

    def _build_panel_empty(self):
        for w in self.right.winfo_children():
            w.destroy()
        ctk.CTkLabel(
            self.right,
            text="✓",
            font=(FONT_FAMILY, 32),
            text_color=COLOR_TEXT_DISABLED,
        ).pack(pady=(48, SPACE_SM))
        ctk.CTkLabel(
            self.right,
            text="Pilih issue di kiri untuk input alasan",
            font=FONT_BODY, text_color=COLOR_TEXT_MUTED,
        ).pack(padx=SPACE_LG)
        if self._last_counts is not None:
            c = self._last_counts
            ctk.CTkLabel(
                self.right,
                text=f"Open {c['open']} · Resolved {c['resolved']} · Total {c['total']}",
                font=FONT_SMALL, text_color=COLOR_TEXT_MUTED,
            ).pack(pady=(SPACE_SM, 0), padx=SPACE_LG)

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

        labels = self._category_labels()
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
            feedback.show_warning(
                self, "Pilih kategori", "Belum memilih kategori alasan.")
            return
        detail = (self.detail_entry.get().strip()
                  if cat in REASON_NEEDS_DETAIL else None) or None
        with get_connection(self._db_path()) as conn:
            set_reason(conn, attendance_id=self.selected_id,
                       category=cat, detail=detail)
        self._notify_data_changed()
        self._reload()
        self._build_panel_empty()
        self.selected_id = None

    def _on_unresolve(self):
        if self.selected_id is None:
            return
        confirmed = feedback.ask_yes_no(
            self, "Konfirmasi",
            "Batalkan resolve?\n\n"
            "Kategori dan detail alasan akan dihapus.\n"
            "Issue akan kembali ke status Open.",
        )
        if not confirmed:
            return
        with get_connection(self._db_path()) as conn:
            unresolve_issue(conn, attendance_id=self.selected_id)
        self._notify_data_changed()
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
        # No default_week → a malformed week key falls back to the full
        # month, which is the exact historical behavior of these screens.
        start, end, _num = resolve_period(self._current_month, self.nav.active)
        return start, end

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
            values = (row["nama"], row["dept"] or "-", row["tanggal"],
                      row["hari"] or "-", row["masuk"] or "—",
                      row["keluar"] or "—") + self._extra_row_values(row)
            if is_resolved:
                try:
                    alasan = render_alasan_ijin(row["reason_category"], row["reason_detail"])
                except Exception:
                    alasan = row["reason_category"] or "-"
                self.resolved_tree.insert(
                    "", "end", iid=str(row["id"]),
                    values=values + (alasan,),
                    tags=("resolved_row",),
                )
                visible_resolved += 1
            else:
                self.open_tree.insert(
                    "", "end", iid=str(row["id"]),
                    values=values,
                    tags=("open_row",),
                )
                visible_open += 1
        self._search.set_count(visible_open + visible_resolved, total_open + total_resolved)

    def _apply_filter(self, query: str):
        # Skip the treeview rebuild when the EFFECTIVE query (matching is
        # case/whitespace-insensitive) didn't change — the debounced
        # KeyRelease also fires for modifier/navigation keys.
        if query.lower().strip() == self._search_query.lower().strip():
            self._search_query = query
            return
        self._search_query = query
        self._render_rows(query)

    def _reload(self):
        start, end = self._active_range()
        self._row_cache = {}

        with get_connection(self._db_path()) as conn:
            counts = self._count_rows(conn, start, end)
            open_rows = self._list_rows(conn, start, end, resolved=False)
            resolved_rows = self._list_rows(conn, start, end, resolved=True)

        self._render_stats(counts)

        for r in open_rows:
            d = dict(r)
            self._row_cache[d["id"]] = d

        for r in resolved_rows:
            d = dict(r)
            self._row_cache[d["id"]] = d

        self._render_rows(self._search_query)
