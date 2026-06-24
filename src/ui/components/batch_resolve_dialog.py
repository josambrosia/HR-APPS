"""Modal dialog — resolve multiple open issues for one employee at once.

Pick an employee, check the dates with open issues (default all checked),
choose one reason category (+ optional detail), and apply it to every
checked date via the existing set_reason DB function.
"""
from typing import Callable, Optional

import customtkinter as ctk
from tkinter import messagebox

from src.config import DB_PATH
from src.db.connection import get_connection
from src.core.session_state import notify_data_changed
from src.db.attendance import set_reason, list_issues_for_period
from src.core.reason_mapper import REASON_LABELS, REASON_NEEDS_DETAIL
from src.ui.theme import (
    COLOR_BG, COLOR_SURFACE, COLOR_SURFACE_HIGH,
    COLOR_BORDER,
    COLOR_ACCENT, COLOR_ACCENT_HOVER,
    COLOR_INFO,
    COLOR_TEXT, COLOR_TEXT_DIM, COLOR_TEXT_MUTED,
    FONT_HEADING, FONT_BODY, FONT_BODY_BOLD, FONT_SMALL, FONT_LABEL,
    SPACE_XS, SPACE_SM, SPACE_MD, SPACE_LG, SPACE_XL,
    RADIUS_MD,
)

DIALOG_W = 520
DIALOG_H = 600
_SCREEN_BUFFER = 100

_MONTH_ID = {
    1: "Januari", 2: "Februari", 3: "Maret", 4: "April", 5: "Mei", 6: "Juni",
    7: "Juli", 8: "Agustus", 9: "September", 10: "Oktober",
    11: "November", 12: "Desember",
}


def _format_tanggal(iso: str, hari: Optional[str]) -> str:
    """'2026-04-06', 'Senin' -> 'Senin, 6 April 2026'."""
    try:
        y, m, d = iso.split("-")
        label = f"{int(d)} {_MONTH_ID[int(m)]} {y}"
    except (ValueError, KeyError):
        return iso
    return f"{hari}, {label}" if hari else label


def group_open_issues_by_employee(issue_rows) -> list:
    """Group open-issue rows (from list_issues_for_period(resolved=False))
    by employee. Returns a list of dicts sorted by nama:
      {employee_id, nama, dept, no_staff,
       issues: [{attendance_id, tanggal, hari, masuk, keluar}, ...]}
    """
    by_emp = {}
    for r in issue_rows:
        eid = r["employee_id"]
        if eid not in by_emp:
            by_emp[eid] = {
                "employee_id": eid,
                "nama": r["nama"],
                "dept": r["dept"],
                "no_staff": r["no_staff"],
                "issues": [],
            }
        by_emp[eid]["issues"].append({
            "attendance_id": r["id"],
            "tanggal": r["tanggal"],
            "hari": r["hari"],
            "masuk": r["masuk"],
            "keluar": r["keluar"],
        })
    return sorted(by_emp.values(), key=lambda e: e["nama"])


def apply_batch_resolve(conn, attendance_ids: list, category: str,
                        detail: Optional[str]) -> int:
    """Resolve each attendance_id with the given category + detail via
    set_reason. Returns the count resolved. get_connection auto-commits on clean block exit."""
    for aid in attendance_ids:
        set_reason(conn, attendance_id=aid, category=category, detail=detail)
    return len(attendance_ids)


class BatchResolveDialog(ctk.CTkToplevel):
    """Modal — resolve many open issues for one employee in one action."""

    def __init__(self, parent, *, period_start: str, period_end: str,
                 on_done: Callable[[], None], lister_fn=None):
        super().__init__(parent)
        self.title("Resolve Massal")
        self.resizable(False, False)
        self.configure(fg_color=COLOR_BG)
        self.transient(parent)

        sh = self.winfo_screenheight()
        sw = self.winfo_screenwidth()
        h = min(DIALOG_H, sh - _SCREEN_BUFFER)
        w = DIALOG_W
        x = (sw - w) // 2
        y = max(0, (sh - h) // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

        # v15.3: 3-row grid on the toplevel itself — header (row 0, fixed),
        # scrollable content (row 1, weight=1 expands), footer (row 2, fixed).
        # The footer cannot be displaced by content overflow because the
        # middle row scrolls when content exceeds its allocated space.
        # No propagate(False) calls — letting Tk size naturally is fine when
        # the footer is in a structural grid slot that can't be pushed off.
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)  # header — fixed
        self.grid_rowconfigure(1, weight=1)  # content — expands & scrolls
        self.grid_rowconfigure(2, weight=0)  # footer — fixed

        self._on_done = on_done
        self._lister_fn = lister_fn or (
            lambda c, s, e: list_issues_for_period(c, s, e, resolved=False))

        with get_connection(DB_PATH) as conn:
            rows = self._lister_fn(conn, period_start, period_end)
        self._groups = group_open_issues_by_employee(rows)
        self._by_label = {
            f"{g['nama']} ({g['dept'] or '-'}) — {len(g['issues'])} issue terbuka": g
            for g in self._groups
        }

        self._date_vars: dict = {}
        self._label_to_key = {v: k for k, v in REASON_LABELS.items()}

        self._build()

        self.after(50, lambda: (self.grab_set(), self.focus_set()))
        self.bind("<Escape>", lambda _e: self._on_cancel())
        self.bind("<Return>", lambda _e: (self._on_submit(), "break")[1])
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

    # Grid row constants for the toplevel itself. Three rows — header
    # (fixed at top), content (scrollable middle, expands), footer (fixed
    # at bottom). The footer's row index is structural and cannot be
    # displaced by anything happening inside content.
    ROW_HEADER  = 0  # weight=0 — header
    ROW_CONTENT = 1  # weight=1 — scrollable middle (CTkScrollableFrame)
    ROW_FOOTER  = 2  # weight=0 — footer (btn_row)

    def _build(self):
        """Build the dialog using header/scrollable-middle/footer architecture.

        v15.3 architectural pivot after three failed pack/grid attempts:
        - v15.0 Task A: side='bottom' reflow trick — failed (Tk skips reflow).
        - v15.1: side='top' natural flow — failed (toplevel auto-grew past
          requested geometry, btn_row fell off the visible bottom).
        - v15.2: single-grid-on-toplevel with spacer row — failed (dialog
          STILL grew past geometry, screenshot showed visible area ~862px
          for a 600px request; pack_propagate(False) / grid_propagate(False)
          didn't actually lock the window size on this customtkinter build).

        v15.3 stops fighting the toplevel sizing. Structure:
            Row 0: header (heading + subtitle) — fixed
            Row 1: content (CTkScrollableFrame) — scrolls if too tall
            Row 2: footer (btn_row with Resolve + Batal + preview) — fixed
        If the toplevel grows in any direction, header and footer remain
        at the top and bottom respectively, and the middle scrolls.
        If the toplevel shrinks (DPI scaling, screen too small), same
        result — middle scrolls. btn_row is mechanically pinned to row 2.
        """
        # === Row 0: Header (always shown) ===
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=self.ROW_HEADER, column=0, sticky="ew",
                    padx=SPACE_XL, pady=(SPACE_LG, SPACE_MD))
        ctk.CTkLabel(
            header, text="Resolve Massal",
            font=FONT_HEADING, text_color=COLOR_TEXT, anchor="w",
        ).pack(anchor="w", fill="x")
        ctk.CTkLabel(
            header,
            text="Selesaikan beberapa issue sekaligus untuk satu karyawan.",
            font=FONT_BODY, text_color=COLOR_TEXT_DIM, anchor="w",
        ).pack(anchor="w", fill="x", pady=(SPACE_XS, 0))

        # === Row 2: Footer FIRST (so it's in the grid before content can
        # affect anything). btn_row holds Resolve + Batal + preview label. ===
        self._btn_row = ctk.CTkFrame(self, fg_color="transparent")
        self._btn_row.grid(row=self.ROW_FOOTER, column=0, sticky="ew",
                           padx=SPACE_XL, pady=(SPACE_MD, SPACE_LG))

        if not self._groups:
            # Empty state — single Tutup button, no scrollable content.
            ctk.CTkButton(
                self._btn_row, text="Tutup", command=self._on_cancel,
                fg_color="transparent", border_width=1, border_color=COLOR_INFO,
                text_color=COLOR_INFO, hover_color=COLOR_SURFACE_HIGH,
                width=160, height=40, font=FONT_BODY_BOLD, corner_radius=RADIUS_MD,
            ).pack(side="right")
            ctk.CTkLabel(
                self, text="Tidak ada issue terbuka di periode ini.",
                font=FONT_BODY, text_color=COLOR_TEXT_MUTED,
            ).grid(row=self.ROW_CONTENT, column=0, sticky="nsew",
                   padx=SPACE_XL, pady=60)
            return

        # Footer buttons (normal case)
        self._submit_btn = ctk.CTkButton(
            self._btn_row, text="Resolve", command=self._on_submit,
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
            text_color=COLOR_BG, width=200, height=40, font=FONT_BODY_BOLD,
            corner_radius=RADIUS_MD)
        self._submit_btn.pack(side="right")
        ctk.CTkButton(
            self._btn_row, text="Batal", command=self._on_cancel,
            fg_color="transparent", hover_color=COLOR_SURFACE_HIGH,
            border_width=1, border_color=COLOR_INFO, text_color=COLOR_INFO,
            width=120, height=40, font=FONT_BODY_BOLD, corner_radius=RADIUS_MD,
        ).pack(side="right", padx=(0, SPACE_MD))
        self._preview = ctk.CTkLabel(
            self._btn_row, text="0 tanggal dipilih", font=FONT_SMALL,
            text_color=COLOR_TEXT_DIM)
        self._preview.pack(side="left")

        # === Row 1: Scrollable content (everything between header and footer) ===
        # Using CTkScrollableFrame here means if the toplevel ends up smaller
        # than the natural content size, content scrolls rather than pushing
        # the footer off-screen.
        content = ctk.CTkScrollableFrame(self, fg_color="transparent")
        content.grid(row=self.ROW_CONTENT, column=0, sticky="nsew",
                     padx=SPACE_XL, pady=0)

        # KARYAWAN
        ctk.CTkLabel(content, text="KARYAWAN", font=FONT_LABEL,
                     text_color=COLOR_TEXT_MUTED, anchor="w").pack(
            anchor="w", fill="x", pady=(0, SPACE_XS))
        self._emp_var = ctk.StringVar(value="")
        ctk.CTkComboBox(
            content, values=list(self._by_label.keys()),
            variable=self._emp_var,
            command=self._on_employee_change,
            fg_color=COLOR_SURFACE_HIGH, button_color=COLOR_ACCENT,
            button_hover_color=COLOR_ACCENT_HOVER, border_color=COLOR_BORDER,
            text_color=COLOR_TEXT, font=FONT_BODY,
        ).pack(anchor="w", fill="x", pady=(0, SPACE_MD))

        # TANGGAL — dates_scroll wrapped in a fixed-height container so
        # the inner scrollable can't push subsequent widgets down.
        ctk.CTkLabel(content, text="TANGGAL DENGAN ISSUE TERBUKA",
                     font=FONT_LABEL, text_color=COLOR_TEXT_MUTED,
                     anchor="w").pack(anchor="w", fill="x", pady=(0, SPACE_XS))
        dates_container = ctk.CTkFrame(content, fg_color="transparent",
                                       height=160)
        dates_container.pack(fill="x", pady=(0, SPACE_MD))
        dates_container.pack_propagate(False)
        self._dates_scroll = ctk.CTkScrollableFrame(
            dates_container, fg_color=COLOR_SURFACE)
        self._dates_scroll.pack(fill="both", expand=True)

        # KATEGORI
        ctk.CTkLabel(content, text="KATEGORI ALASAN", font=FONT_LABEL,
                     text_color=COLOR_TEXT_MUTED, anchor="w").pack(
            anchor="w", fill="x", pady=(0, SPACE_XS))
        self._cat_var = ctk.StringVar(value="")
        ctk.CTkComboBox(
            content, values=list(REASON_LABELS.values()),
            variable=self._cat_var,
            command=self._on_cat_change,
            fg_color=COLOR_SURFACE_HIGH, button_color=COLOR_ACCENT,
            button_hover_color=COLOR_ACCENT_HOVER, border_color=COLOR_BORDER,
            text_color=COLOR_TEXT, font=FONT_BODY,
        ).pack(anchor="w", fill="x", pady=(0, SPACE_XS))

        # Detail frame — packed inside content. Its children toggle via
        # pack/pack_forget but the frame itself stays in the content flow.
        # Since it's INSIDE the scrollable middle, any growth here just
        # scrolls — the footer in ROW_FOOTER is untouched.
        self._detail_frame = ctk.CTkFrame(content, fg_color="transparent")
        self._detail_frame.pack(anchor="w", fill="x", pady=0)
        self._detail_label = ctk.CTkLabel(
            self._detail_frame, text="Detail:", font=FONT_SMALL,
            text_color=COLOR_TEXT_MUTED)
        self._detail_entry = ctk.CTkEntry(
            self._detail_frame,
            fg_color=COLOR_SURFACE_HIGH, border_width=1,
            border_color=COLOR_BORDER, text_color=COLOR_TEXT, font=FONT_BODY)

    def _on_employee_change(self, _label):
        for w in self._dates_scroll.winfo_children():
            w.destroy()
        self._date_vars = {}
        group = self._by_label.get(self._emp_var.get())
        if not group:
            return
        for iss in group["issues"]:
            var = ctk.BooleanVar(value=True)   # default all checked
            self._date_vars[iss["attendance_id"]] = var
            row = ctk.CTkFrame(self._dates_scroll, fg_color=COLOR_SURFACE_HIGH,
                               corner_radius=RADIUS_MD)
            row.pack(fill="x", pady=2, padx=2)
            ctk.CTkCheckBox(
                row, text="", width=24, variable=var,
                command=self._update_preview,
                fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
            ).pack(side="left", padx=(SPACE_SM, SPACE_XS), pady=SPACE_XS)
            info = (f"{_format_tanggal(iss['tanggal'], iss['hari'])}    "
                    f"masuk {iss['masuk'] or '—'} · keluar {iss['keluar'] or '—'}")
            ctk.CTkLabel(row, text=info, font=FONT_SMALL, text_color=COLOR_TEXT,
                         anchor="w").pack(side="left", fill="x", expand=True,
                                          pady=SPACE_XS)
        self._update_preview()

    def _on_cat_change(self, _label):
        """Show / hide the detail label + entry inside _detail_frame.

        v15.3: _detail_frame lives inside the scrollable middle content,
        completely separate from the footer's grid row. Toggling its
        children pack/pack_forget can only affect content layout — at
        worst it adds a scrollable row. The footer (btn_row in ROW_FOOTER)
        is structurally untouched.
        """
        key = self._label_to_key.get(self._cat_var.get(), "")
        self._detail_label.pack_forget()
        self._detail_entry.pack_forget()
        if key in REASON_NEEDS_DETAIL:
            self._detail_label.pack(anchor="w")
            self._detail_entry.pack(anchor="w", fill="x", pady=(SPACE_XS, 0))

    def _checked_ids(self) -> list:
        return [aid for aid, var in self._date_vars.items() if var.get()]

    def _update_preview(self):
        n = len(self._checked_ids())
        self._preview.configure(text=f"{n} tanggal dipilih")
        self._submit_btn.configure(text=f"Resolve {n} Issue" if n else "Resolve")

    def _on_submit(self):
        ids = self._checked_ids()
        if not ids:
            messagebox.showwarning("Pilih tanggal",
                                   "Belum ada tanggal yang dipilih.")
            return
        cat = self._label_to_key.get(self._cat_var.get(), "")
        if cat not in REASON_LABELS:
            messagebox.showwarning("Pilih kategori",
                                   "Belum memilih kategori alasan.")
            return
        detail = (self._detail_entry.get().strip()
                  if cat in REASON_NEEDS_DETAIL else None) or None
        with get_connection(DB_PATH) as conn:
            apply_batch_resolve(conn, ids, cat, detail)
        notify_data_changed()
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()
        self._on_done()

    def _on_cancel(self):
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()
