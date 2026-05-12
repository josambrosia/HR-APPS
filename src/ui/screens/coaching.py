"""Coaching screen — weekly view of pegawai over lateness threshold with
one-click toggle to mark coached and optional notes panel."""
from tkinter import ttk
import customtkinter as ctk

from src.config import DB_PATH
from src.core.week_utils import weeks_in_month
from src.db.coaching import (
    list_coaching_for_week, mark_coached, unmark_coached,
    get_coaching_notes, update_notes,
)
from src.db.connection import get_connection
from src.db.settings import get_setting
from src.ui.components.kpi_card import KPICard
from src.ui.components.week_nav import WeekNavBar
from src.ui.theme import (
    FONT_FAMILY, COLOR_OK, COLOR_WARN, COLOR_ACCENT,
    COLOR_PANEL, COLOR_TEXT, COLOR_TEXT_DIM,
)


class CoachingScreen(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self.grid_columnconfigure(0, weight=2)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=1)

        with get_connection(DB_PATH) as conn:
            self._current_month = get_setting(conn, "current_month") or ""
            threshold_raw = get_setting(conn, "coaching_threshold_min") or "75"
            try:
                self._threshold = int(threshold_raw)
            except ValueError:
                self._threshold = 75

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
            background=COLOR_PANEL, fieldbackground=COLOR_PANEL,
            foreground=COLOR_TEXT, rowheight=28, borderwidth=0,
        )
        style.configure(
            "Coaching.Treeview.Heading",
            background="#2C1B47", foreground=COLOR_TEXT_DIM,
            relief="flat", font=(FONT_FAMILY, 10, "bold"),
        )
        style.map(
            "Coaching.Treeview",
            background=[("selected", COLOR_ACCENT)],
            foreground=[("selected", "#1E104E")],
        )

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        ctk.CTkLabel(header, text="🎯 Coaching",
                     font=(FONT_FAMILY, 24, "bold"),
                     text_color=COLOR_TEXT).pack(side="left", padx=(0, 16))
        self.nav = WeekNavBar(
            header, current_month=self._current_month,
            on_change=self._on_period_change, initial="minggu_1",
            include_all=False,
        )
        self.nav.pack(side="left")

    def _on_period_change(self, _key):
        self._reload()

    def _build_stats(self):
        self.stats = ctk.CTkFrame(self, fg_color="transparent")
        self.stats.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 12))
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
            coverage = f"{round(sudah / total * 100)}%"
        else:
            coverage = "—"

        cards = [
            ("Total", str(total), COLOR_ACCENT),
            ("Sudah", str(sudah), COLOR_OK),
            ("Belum", str(belum), COLOR_WARN),
            ("Coverage", coverage, COLOR_OK if total == 0 or sudah == total else COLOR_TEXT),
        ]
        for i, (label, val, color) in enumerate(cards):
            c = KPICard(self.stats, label, val, value_color=color)
            c.grid(row=0, column=i, padx=4, sticky="ew")
            self._stats_cards.append(c)

    def _build_table_and_panel(self):
        left = ctk.CTkFrame(self, fg_color="transparent")
        left.grid(row=2, column=0, sticky="nsew", padx=(0, 12))
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(0, weight=1)

        cols = ["nama", "dept", "terlambat", "status", "aksi"]
        widths = {"nama": 130, "dept": 100, "terlambat": 90, "status": 110, "aksi": 110}
        labels = {"nama": "Nama", "dept": "Dept", "terlambat": "Terlambat",
                  "status": "Status", "aksi": "Aksi"}

        self.tree = ttk.Treeview(
            left, columns=cols, show="headings",
            style="Coaching.Treeview", selectmode="browse", height=12,
        )
        for c in cols:
            self.tree.heading(c, text=labels[c])
            self.tree.column(c, width=widths[c], anchor="w")
        # Tag-based row tinting
        self.tree.tag_configure("belum", background="#3F2A2C", foreground=COLOR_TEXT)
        self.tree.tag_configure("sudah", background="#2A3F30", foreground=COLOR_TEXT)
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.bind("<Button-1>", self._on_tree_click)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        right = ctk.CTkFrame(self, fg_color=COLOR_PANEL, corner_radius=8)
        right.grid(row=2, column=1, sticky="nsew")
        self.right = right
        self._build_panel_empty()

    def _build_panel_empty(self):
        for w in self.right.winfo_children():
            w.destroy()
        ctk.CTkLabel(
            self.right,
            text="Pilih baris untuk lihat detail\natau klik kolom Aksi untuk\nubah status coaching.",
            justify="center",
            font=(FONT_FAMILY, 12), text_color=COLOR_TEXT_DIM
        ).pack(pady=80, padx=16)

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
            raw_rows = list_coaching_for_week(
                conn, week_start=start, week_end=end,
                threshold_minutes=self._threshold,
            )
        rows = [dict(r) for r in raw_rows]
        self._render_stats(rows)

        for r in rows:
            iid = str(r["employee_id"])
            self._row_cache[iid] = r
            is_coached = bool(r["is_coached"])
            status_text = "✓ Sudah" if is_coached else "○ Belum"
            aksi_text = "⊖ Batalkan" if is_coached else "⊕ Tandai"
            tag = "sudah" if is_coached else "belum"
            self.tree.insert(
                "", "end", iid=iid,
                values=(
                    r["nama"], r["dept"] or "-",
                    f"{r['total_terlambat']} mnt",
                    status_text, aksi_text,
                ),
                tags=(tag,),
            )

    def _on_tree_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        column = self.tree.identify_column(event.x)
        row_iid = self.tree.identify_row(event.y)
        if region != "cell" or not row_iid:
            return
        # Aksi column is the 5th column → "#5"
        if column == "#5":
            self._toggle_row(row_iid)
            return "break"  # prevent selection event

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
                     font=(FONT_FAMILY, 12), text_color=COLOR_TEXT
                     ).pack(anchor="w", padx=16, pady=(16, 12))

        is_coached = bool(row["is_coached"])
        status_color = COLOR_OK if is_coached else COLOR_WARN
        status_lines = ["Status: " + ("✓ Sudah Coaching" if is_coached else "○ Belum Coaching")]
        if is_coached and row.get("coached_at"):
            status_lines.append(f"Tercatat: {row['coached_at']}")
        ctk.CTkLabel(self.right, text="\n".join(status_lines), justify="left",
                     font=(FONT_FAMILY, 11), text_color=status_color
                     ).pack(anchor="w", padx=16, pady=(0, 12))

        ctk.CTkLabel(self.right, text="Catatan (opsional):",
                     font=(FONT_FAMILY, 11), text_color=COLOR_TEXT_DIM
                     ).pack(anchor="w", padx=16)

        notes_box = ctk.CTkTextbox(self.right, width=300, height=110)
        notes_box.pack(anchor="w", padx=16, pady=(4, 8))

        if is_coached:
            existing = ""
            with get_connection(DB_PATH) as conn:
                existing = get_coaching_notes(
                    conn, employee_id=row["employee_id"], week_start=start,
                ) or ""
            notes_box.insert("1.0", existing)
            save_btn = ctk.CTkButton(
                self.right, text="Simpan Catatan",
                fg_color=COLOR_OK, text_color="#1E104E", width=300,
                command=lambda: self._on_save_notes(row, notes_box.get("1.0", "end").strip()),
            )
            save_btn.pack(anchor="w", padx=16, pady=8)
        else:
            notes_box.insert("1.0", "(Tandai Sudah Coaching dulu untuk simpan catatan)")
            notes_box.configure(state="disabled")

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
