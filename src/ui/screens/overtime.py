"""Layar Lembur (v26): daftar deteksi + verifikasi.

Deteksi dihitung ulang dari absensi + jadwal tanggal (src/core/overtime.py).
Keputusan verifikasi (Open → Diajukan → Diterima/Tidak Diterima) disimpan di
tabel overtime_decisions lewat dialog detail. Mengikuti pola layar v22:
on_show re-read tanpa rebuild chrome, search debounce, toast/feedback gelap.
"""
import os
import tempfile
from pathlib import Path

import customtkinter as ctk
from tkinter import ttk

from src.config import DB_PATH
from src.core.overtime import count_pending, format_duration, month_rows, summarize
from src.core.session_state import data_version, notify_data_changed
from src.core.week_utils import MONTH_NAMES_ID
from src.db.connection import get_connection
from src.db.overtime import apply_status
from src.db.settings import get_setting
from src.ui import feedback, motion
from src.ui.browser_launcher import open_html_in_browser
from src.ui.components.active_month_banner import ActiveMonthBanner
from src.ui.components.kpi_card import KPICard
from src.ui.components.overtime_detail_dialog import OvertimeDetailDialog
from src.ui.components.overtime_print_dialog import OvertimePrintDialog
from src.ui.components.search_bar import SearchBar
from src.ui.components.toast import show_success_toast
from src.ui.components.tree_style import (
    RowHover, apply_zebra_tags, style_treeview,
)
from src.ui.tasks import BusyGuard
from src.ui.theme import (
    COLOR_BG, COLOR_SURFACE, COLOR_SURFACE_HIGH, COLOR_BORDER,
    COLOR_ACCENT, COLOR_ACCENT_HOVER, COLOR_INFO, COLOR_SUCCESS, COLOR_WARN,
    COLOR_ERROR, COLOR_TEXT, COLOR_TEXT_DIM, COLOR_TEXT_MUTED,
    COLOR_ROW_TINT_BELUM,
    FONT_DISPLAY, FONT_BODY, FONT_BODY_BOLD, FONT_SMALL, FONT_LABEL,
    SPACE_XS, SPACE_SM, SPACE_MD, SPACE_LG, SPACE_XL, RADIUS_MD,
)

SEARCH_DEBOUNCE_MS = 200

STATUS_FILTERS = [
    ("all", "Semua"),
    ("open", "Open"),
    ("diajukan", "Diajukan"),
    ("diterima", "Diterima"),
    ("tidak_diterima", "Tidak Diterima"),
]
STATUS_LABELS = dict(STATUS_FILTERS)
STATUS_COLORS = {
    "open": COLOR_WARN,
    "diajukan": COLOR_INFO,
    "diterima": COLOR_SUCCESS,
    "tidak_diterima": COLOR_ERROR,
}
CHECK_OFF = "☐"
CHECK_ON = "☑"

COLUMNS = [
    ("pilih", "", 32, False),
    ("tanggal", "Tanggal", 92, False),
    ("nama", "Nama", 150, False),
    ("dept", "Dept", 96, False),
    ("masuk", "Masuk", 62, True),
    ("keluar", "Keluar", 62, True),
    ("lembur", "Jam Lembur", 86, True),
    ("disetujui", "Disetujui", 80, True),
    ("status", "Status", 96, False),
    ("catatan", "Catatan", 170, False),
]


def _month_label(year_month: str) -> str:
    try:
        y, m = year_month.split("-")
        return f"{MONTH_NAMES_ID[int(m)]} {y}"
    except (ValueError, KeyError):
        return year_month


class OvertimeScreen(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        style_treeview("Overtime.Treeview", rowheight=26)
        style_treeview("OvertimeSummary.Treeview", rowheight=24)
        self._rows = []
        self._row_by_iid = {}
        self._checked: set[str] = set()
        self._filter = "all"
        self._anim_sig = motion.RenderSignature()

        with get_connection(DB_PATH) as conn:
            self._month = _read_month(conn)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)
        self._build_header()
        self._build_kpis()
        self._build_toolbar()
        self._build_body()
        self._search.install_shortcuts(self)
        self._reload()

    # ---------- build ----------
    def _build_header(self):
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", pady=(0, SPACE_SM))
        ctk.CTkLabel(head, text="Lembur", font=FONT_DISPLAY,
                     text_color=COLOR_TEXT).pack(side="left")
        self._print_btn = ctk.CTkButton(
            head, text="🖨️  Cetak", command=self._open_print, width=104,
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
            text_color=COLOR_BG, font=FONT_BODY_BOLD, corner_radius=RADIUS_MD)
        self._print_btn.pack(side="right")
        self._badge = ActiveMonthBanner(
            head, variant="badge",
            value=_month_label(self._month) if self._month else "")
        if self._month:
            self._badge.pack(side="right", padx=(0, SPACE_SM))

    def _build_kpis(self):
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.grid(row=1, column=0, sticky="ew", pady=(0, SPACE_SM))
        for i in range(4):
            frame.grid_columnconfigure(i, weight=1)
        self._kpi_orang = KPICard(frame, "Pegawai Lembur", "0")
        self._kpi_detected = KPICard(frame, "Jam Terdeteksi", "0m")
        self._kpi_approved = KPICard(frame, "Jam Disetujui", "0m",
                                     COLOR_SUCCESS)
        self._kpi_pending = KPICard(frame, "Belum Diproses", "0", COLOR_WARN)
        for i, card in enumerate((self._kpi_orang, self._kpi_detected,
                                  self._kpi_approved, self._kpi_pending)):
            card.grid(row=0, column=i, sticky="ew",
                      padx=(0 if i == 0 else SPACE_XS, 0))

    def _build_toolbar(self):
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.grid(row=2, column=0, sticky="ew", pady=(0, SPACE_SM))
        bar = ctk.CTkFrame(container, fg_color="transparent")
        bar.pack(fill="x")
        self._filter_ctl = ctk.CTkSegmentedButton(
            bar, values=[label for _s, label in STATUS_FILTERS],
            command=self._on_filter,
            fg_color=COLOR_SURFACE_HIGH, selected_color=COLOR_ACCENT,
            selected_hover_color=COLOR_ACCENT_HOVER,
            unselected_color=COLOR_SURFACE_HIGH,
            unselected_hover_color=COLOR_BORDER,
            text_color=COLOR_TEXT, font=FONT_SMALL, corner_radius=RADIUS_MD)
        self._filter_ctl.pack(side="left")
        self._filter_ctl.set(STATUS_LABELS["all"])
        self._search = SearchBar(
            bar, on_change=self._on_search, width=230,
            debounce_ms=SEARCH_DEBOUNCE_MS)
        self._search.pack(side="right")

        self._batch_bar = ctk.CTkFrame(
            container, fg_color=COLOR_SURFACE, border_width=1,
            border_color=COLOR_BORDER, corner_radius=RADIUS_MD)
        self._batch_label = ctk.CTkLabel(
            self._batch_bar, text="", font=FONT_SMALL,
            text_color=COLOR_TEXT_DIM)
        self._batch_label.pack(side="left", padx=SPACE_MD)
        for text, status, color in (
                ("Ajukan", "diajukan", COLOR_ACCENT),
                ("Terima", "diterima", COLOR_SUCCESS),
                ("Tolak", "tidak_diterima", COLOR_ERROR)):
            ctk.CTkButton(
                self._batch_bar, text=text, width=76,
                command=lambda s=status: self._apply_batch(s),
                fg_color=color, hover_color=COLOR_ACCENT_HOVER,
                text_color=COLOR_BG, font=FONT_SMALL, corner_radius=RADIUS_MD,
            ).pack(side="left", padx=(0, SPACE_XS))
        ctk.CTkButton(
            self._batch_bar, text="Bersihkan", width=84,
            command=self._clear_checks,
            fg_color="transparent", border_width=1, border_color=COLOR_INFO,
            text_color=COLOR_INFO, hover_color=COLOR_SURFACE_HIGH,
            font=FONT_SMALL, corner_radius=RADIUS_MD,
        ).pack(side="left")

    def _build_body(self):
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=3, column=0, sticky="nsew")
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(body, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, SPACE_SM))
        left.grid_rowconfigure(0, weight=1)
        left.grid_columnconfigure(0, weight=1)
        cols = [c[0] for c in COLUMNS]
        self.tree = ttk.Treeview(
            left, columns=cols, show="headings", style="Overtime.Treeview",
            selectmode="none")
        for cid, label, width, right in COLUMNS:
            self.tree.heading(cid, text=label)
            self.tree.column(cid, width=width, anchor="e" if right else "w",
                             stretch=(cid in ("nama", "catatan")))
        self.tree.grid(row=0, column=0, sticky="nsew")
        apply_zebra_tags(self.tree)
        self._hover = RowHover(self.tree)
        self.tree.bind("<Button-1>", self._on_tree_click)

        right = ctk.CTkFrame(body, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(right, text="RINGKASAN PER KARYAWAN",
                     font=FONT_LABEL, text_color=COLOR_TEXT_MUTED,
                     anchor="w").grid(row=0, column=0, sticky="ew",
                                      pady=(0, SPACE_XS))
        self.sum_tree = ttk.Treeview(
            right, columns=("nama", "hari", "det", "app"), show="headings",
            style="OvertimeSummary.Treeview", selectmode="none")
        for cid, label, width, right_al in (
                ("nama", "Nama", 110, False), ("hari", "Hari", 40, True),
                ("det", "Terdeteksi", 70, True), ("app", "Disetujui", 70, True)):
            self.sum_tree.heading(cid, text=label)
            self.sum_tree.column(cid, width=width,
                                 anchor="e" if right_al else "w")
        self.sum_tree.grid(row=1, column=0, sticky="nsew")
        apply_zebra_tags(self.sum_tree)

    # ---------- data ----------
    def _filtered_rows(self):
        q = self._search.get().strip().lower()
        out = []
        for r in self._rows:
            if self._filter != "all" and r.status != self._filter:
                continue
            if q and q not in r.nama.lower():
                continue
            out.append(r)
        return out

    def _reload(self, flash_iids=None):
        with get_connection(DB_PATH) as conn:
            self._rows = month_rows(conn, self._month) if self._month else []
        self._checked.clear()
        self._row_by_iid = {
            f"{r.employee_id}|{r.tanggal}": r for r in self._rows}
        self._update_kpis()
        self._update_tabs()
        self._render_table()
        self._render_summary()
        self._update_batch_bar()
        if flash_iids:
            for iid in flash_iids:
                if iid in self._row_by_iid:
                    motion.flash_row(self.tree, iid, COLOR_SUCCESS,
                                     COLOR_ROW_TINT_BELUM)

    def _update_kpis(self):
        rows = self._rows
        names = {r.employee_id for r in rows}
        detected = sum(r.minutes for r in rows)
        approved = sum(r.approved_minutes or 0 for r in rows
                       if r.status == "diterima")
        pending = sum(1 for r in rows if r.status in ("open", "diajukan"))
        self._kpi_orang.set_value(str(len(names)))
        self._kpi_detected.set_value(format_duration(detected))
        self._kpi_approved.set_value(format_duration(approved))
        self._kpi_pending.set_value(str(pending))

    def _update_tabs(self):
        counts = {sid: 0 for sid, _ in STATUS_FILTERS}
        counts["all"] = len(self._rows)
        for r in self._rows:
            counts[r.status] = counts.get(r.status, 0) + 1
        labels = [f"{label} ({counts[sid]})" for sid, label in STATUS_FILTERS]
        self._filter_ctl.configure(values=labels)
        self._filter_ctl.set(labels[[s for s, _ in STATUS_FILTERS].index(self._filter)])

    def _render_table(self):
        self.tree.delete(*self.tree.get_children())
        rows = self._filtered_rows()
        for r in rows:
            iid = f"{r.employee_id}|{r.tanggal}"
            tanggal_cell = r.tanggal + (" ⚠" if r.missing_data else "")
            self.tree.insert(
                "", "end", iid=iid,
                values=(
                    CHECK_ON if iid in self._checked else CHECK_OFF,
                    tanggal_cell, r.nama, r.dept or "—",
                    r.masuk or "—", r.keluar or "—",
                    format_duration(r.minutes) if r.qualifies else "—",
                    format_duration(r.approved_minutes)
                    if r.approved_minutes is not None else "—",
                    STATUS_LABELS.get(r.status, r.status),
                    r.note or "",
                ),
                tags=("oddrow",) if len(self.tree.get_children()) % 2 else ("evenrow",))
        self._search.set_count(len(rows), len(self._rows))

    def _render_summary(self):
        self.sum_tree.delete(*self.sum_tree.get_children())
        for a in summarize(self._rows):
            self.sum_tree.insert(
                "", "end",
                values=(a["nama"], a["days"], format_duration(a["detected"]),
                        format_duration(a["approved"])))

    # ---------- interaction ----------
    def _on_filter(self, label):
        for sid, lab in STATUS_FILTERS:
            if label.startswith(lab):
                self._filter = sid
                break
        self._render_table()

    def _on_search(self, _text):
        self._render_table()

    def _on_tree_click(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        iid = self.tree.identify_row(event.y)
        if not iid:
            return
        col = self.tree.identify_column(event.x)
        if col == "#1":
            self._toggle_check(iid)
            return "break"
        row = self._row_by_iid.get(iid)
        if row is not None:
            self._open_detail(row)
            return "break"

    def _toggle_check(self, iid):
        if iid in self._checked:
            self._checked.discard(iid)
        else:
            self._checked.add(iid)
        if self.tree.exists(iid):
            vals = list(self.tree.item(iid, "values"))
            vals[0] = CHECK_ON if iid in self._checked else CHECK_OFF
            self.tree.item(iid, values=vals)
        self._update_batch_bar()

    def _clear_checks(self):
        self._checked.clear()
        for iid in self.tree.get_children():
            vals = list(self.tree.item(iid, "values"))
            vals[0] = CHECK_OFF
            self.tree.item(iid, values=vals)
        self._update_batch_bar()

    def _update_batch_bar(self):
        n = len(self._checked)
        if n:
            self._batch_label.configure(text=f"{n} baris dipilih")
            if not self._batch_bar.winfo_manager():
                self._batch_bar.pack(fill="x", pady=(SPACE_XS, 0))
        else:
            self._batch_bar.pack_forget()

    def _open_detail(self, row):
        OvertimeDetailDialog(self.winfo_toplevel(), row,
                             on_saved=self._on_detail_saved)

    def _on_detail_saved(self):
        self._reload()
        show_success_toast(
            self.winfo_toplevel(), title="Tersimpan",
            message="Status lembur diperbarui — baris yang diubah kini ada "
                    "di tab status barunya.")

    def _apply_batch(self, status):
        if not self._checked:
            return
        eligible = {"diajukan": {"open"},
                    "diterima": {"diajukan"},
                    "tidak_diterima": {"diajukan"}}[status]
        applied, skipped, flashed = 0, 0, []
        with get_connection(DB_PATH) as conn:
            for iid in list(self._checked):
                r = self._row_by_iid.get(iid)
                if r is None or r.status not in eligible:
                    skipped += 1
                    continue
                apply_status(
                    conn, employee_id=r.employee_id, tanggal=r.tanggal,
                    status=status, detected_minutes=r.minutes,
                    approved_minutes=r.minutes if status == "diterima" else None)
                applied += 1
                flashed.append(iid)
        if applied:
            notify_data_changed()
            self._reload(flash_iids=flashed)
        else:
            self._reload()
        label = STATUS_LABELS.get(status, status)
        msg = f"{applied} baris diubah ke {label}."
        if skipped:
            msg += f" {skipped} baris dilewati (status tidak sesuai)."
        show_success_toast(self.winfo_toplevel(), title="Verifikasi massal",
                           message=msg)

    # ---------- print ----------
    def _open_print(self):
        OvertimePrintDialog(self.winfo_toplevel(), on_confirm=self._do_print)

    def _do_print(self, mode):
        guard = BusyGuard(self._print_btn, busy_text="Menyiapkan")
        if not guard.acquire():
            return
        try:
            from src.reports.overtime_print import render_overtime_print_html
            with get_connection(DB_PATH) as conn:
                html = render_overtime_print_html(conn, self._month, mode)
        except Exception as exc:  # noqa: BLE001
            guard.release()
            feedback.show_error(self, "Gagal menyiapkan cetakan", str(exc))
            return
        guard.release()
        fd, path = tempfile.mkstemp(suffix=".html", prefix="lembur_")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(html)
        success, browser = open_html_in_browser(Path(path))
        if success:
            show_success_toast(self.winfo_toplevel(), title="Laporan Dibuka",
                               message=f"Cetak dari {browser} (Ctrl+P / Save PDF).")
        else:
            feedback.show_warning(
                self, "Browser tidak ditemukan",
                "Laporan tersimpan tapi tidak bisa dibuka otomatis.\n"
                f"Buka manual: {path}")

    # ---------- shell hook ----------
    def on_show(self):
        with get_connection(DB_PATH) as conn:
            self._month = _read_month(conn)
        if self._month:
            self._badge.set_value(_month_label(self._month))
            if not self._badge.winfo_manager():
                self._badge.pack(side="right", padx=(0, SPACE_SM))
        else:
            self._badge.pack_forget()
        self._reload()


def _read_month(conn) -> str:
    return get_setting(conn, "current_month", default="") or ""
