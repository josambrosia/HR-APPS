from collections import Counter
from pathlib import Path
from tkinter import filedialog, messagebox
import customtkinter as ctk

from src.config import DB_PATH
from src.db.connection import get_connection
from src.db.employees import upsert_employee, get_employee_by_no_staff
from src.db.attendance import upsert_attendance
from src.db.settings import set_setting
from src.parsers.fingerprint import parse_fingerprint_file
from src.core.issue_detector import is_issue
from src.ui.components.kpi_card import KPICard
from src.ui.components.toast import show_success_toast
from src.ui.theme import (
    FONT_FAMILY,
    COLOR_BG, COLOR_SURFACE_HIGH,
    COLOR_BORDER_STRONG,
    COLOR_ACCENT, COLOR_ACCENT_HOVER,
    COLOR_INFO, COLOR_WARN,
    COLOR_TEXT, COLOR_TEXT_MUTED,
    FONT_DISPLAY, FONT_SUBHEAD,
    FONT_BODY, FONT_BODY_BOLD, FONT_SMALL,
    SPACE_XS, SPACE_SM, SPACE_LG,
    RADIUS_LG,
)


_MONTH_ID = {
    1: "Januari", 2: "Februari", 3: "Maret", 4: "April",
    5: "Mei", 6: "Juni", 7: "Juli", 8: "Agustus",
    9: "September", 10: "Oktober", 11: "November", 12: "Desember",
}


def _format_month_id(month_str: str) -> str:
    """'2026-04' → 'April 2026'. Falls back to the raw string if unparseable."""
    try:
        year_s, m_s = month_str.split("-")
        return f"{_MONTH_ID[int(m_s)]} {year_s}"
    except (ValueError, KeyError):
        return month_str


class ImportScreen(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self._pending_path: Path | None = None
        self._pending_rows: list = []
        self._build()

    def _build(self):
        # Header
        ctk.CTkLabel(
            self, text="Import Fingerprint",
            font=FONT_DISPLAY, text_color=COLOR_TEXT,
        ).pack(anchor="w", pady=(0, SPACE_LG))

        # ── Drop zone ──
        # "#0F0F0F" — one-off, slightly lighter than COLOR_BG for contrast.
        # CTk doesn't support dashed borders; we approximate with a solid
        # COLOR_BORDER_STRONG 2px border + magenta hover state.
        self.dropzone = ctk.CTkFrame(
            self,
            fg_color="#0F0F0F",
            border_width=2,
            border_color=COLOR_BORDER_STRONG,
            corner_radius=RADIUS_LG,
            height=200,
        )
        self.dropzone.pack(fill="x", pady=(0, SPACE_LG))
        self.dropzone.pack_propagate(False)

        # Inner content centered vertically
        inner = ctk.CTkFrame(self.dropzone, fg_color="transparent")
        inner.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(
            inner, text="📥",
            font=(FONT_FAMILY, 28),
            text_color=COLOR_TEXT,
        ).pack()
        ctk.CTkLabel(
            inner, text="Drag file fingerprint .xls ke sini",
            font=FONT_SUBHEAD, text_color=COLOR_TEXT,
        ).pack(pady=(SPACE_SM, SPACE_XS))
        ctk.CTkLabel(
            inner, text="atau klik browse",
            font=FONT_SMALL, text_color=COLOR_TEXT_MUTED,
        ).pack(pady=(0, SPACE_SM))

        ctk.CTkButton(
            inner, text="📁 Browse File",
            command=self._on_pick_file,
            fg_color="transparent",
            border_width=1, border_color=COLOR_INFO,
            text_color=COLOR_INFO,
            hover_color=COLOR_SURFACE_HIGH,
            font=FONT_BODY_BOLD,
        ).pack()

        # Hover state — magenta border highlight (mimics drag affordance).
        # Tk fires Leave when the pointer crosses into a child widget, then
        # Enter again when it returns to the parent — causing flicker. We
        # count nested Enter/Leave on every descendant so the highlight
        # stays on as long as the pointer is anywhere inside the subtree.
        self._dropzone_pointer_inside = 0

        def _on_enter(_e):
            self._dropzone_pointer_inside += 1
            if self._dropzone_pointer_inside > 0:
                self.dropzone.configure(border_color=COLOR_ACCENT)

        def _on_leave(_e):
            self._dropzone_pointer_inside -= 1
            if self._dropzone_pointer_inside <= 0:
                self._dropzone_pointer_inside = 0  # guard underflow
                self.dropzone.configure(border_color=COLOR_BORDER_STRONG)

        def _bind_hover_recursive(widget):
            widget.bind("<Enter>", _on_enter, add="+")
            widget.bind("<Leave>", _on_leave, add="+")
            for child in widget.winfo_children():
                _bind_hover_recursive(child)

        _bind_hover_recursive(self.dropzone)

        # ── Preview cards (populated after file pick) ──
        self.preview_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.preview_frame.pack(fill="x", pady=(0, SPACE_LG))
        self._render_preview_placeholder()

        # ── Action row ──
        action_row = ctk.CTkFrame(self, fg_color="transparent")
        action_row.pack(fill="x")

        self.import_btn = ctk.CTkButton(
            action_row, text="Konfirmasi Impor",
            command=self._on_confirm,
            state="disabled",
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
            text_color=COLOR_BG,
            font=FONT_BODY_BOLD,
        )
        self.import_btn.pack(side="right", padx=(SPACE_SM, 0))

        self.cancel_btn = ctk.CTkButton(
            action_row, text="Batal",
            command=self._on_cancel,
            state="disabled",
            fg_color="transparent",
            border_width=1, border_color=COLOR_INFO,
            text_color=COLOR_INFO,
            hover_color=COLOR_SURFACE_HIGH,
            font=FONT_BODY_BOLD,
        )
        self.cancel_btn.pack(side="right")

    def _render_preview_placeholder(self):
        """Empty-state placeholder before file selection."""
        for child in self.preview_frame.winfo_children():
            child.destroy()
        ctk.CTkLabel(
            self.preview_frame, text="(belum ada file dipilih)",
            font=FONT_BODY, text_color=COLOR_TEXT_MUTED,
        ).pack(anchor="w", pady=SPACE_SM)

    def _render_preview_cards(self, pegawai_count: int, date_range: str,
                              issue_count: int, new_emp_count: int):
        """Render the 4 preview metric cards in a grid."""
        for child in self.preview_frame.winfo_children():
            child.destroy()

        self.preview_frame.grid_columnconfigure(0, weight=1)
        self.preview_frame.grid_columnconfigure(1, weight=1)
        self.preview_frame.grid_columnconfigure(2, weight=1)
        self.preview_frame.grid_columnconfigure(3, weight=1)

        # 4 KPI cards. Date range gets a smaller body-bold font because
        # "2026-04-01 → 2026-04-30" doesn't fit at the default 22pt mono.
        cards = [
            ("Pegawai", str(pegawai_count), COLOR_TEXT, True, None),
            ("Range Tanggal", date_range, COLOR_INFO, False, FONT_BODY_BOLD),
            ("Issue Baru", str(issue_count), COLOR_WARN, True, None),
            ("Pegawai Baru", str(new_emp_count), COLOR_INFO, True, None),
        ]
        for col, (label, value, value_color, mono, value_font) in enumerate(cards):
            KPICard(
                self.preview_frame, label, value,
                value_color=value_color, mono=mono, value_font=value_font,
            ).grid(row=0, column=col, sticky="nsew", padx=SPACE_XS, pady=0)

    def _on_pick_file(self):
        path = filedialog.askopenfilename(
            title="Pilih file fingerprint",
            filetypes=[("Excel", "*.xls *.xlsx"), ("All files", "*.*")],
        )
        if not path:
            return
        self._pending_path = Path(path)
        try:
            self._pending_rows = parse_fingerprint_file(self._pending_path)
        except Exception as e:
            messagebox.showerror("Error parsing", str(e))
            return

        issue_count = sum(1 for r in self._pending_rows if is_issue(r))
        unique_emps = {r.no_staff for r in self._pending_rows}
        dates = sorted({r.tanggal for r in self._pending_rows})
        date_range = f"{dates[0]} → {dates[-1]}" if dates else "(empty)"

        # Detect "new" employees not yet in DB
        new_emp_count = 0
        with get_connection(DB_PATH) as conn:
            for no_staff in unique_emps:
                if get_employee_by_no_staff(conn, no_staff) is None:
                    new_emp_count += 1

        self._render_preview_cards(
            pegawai_count=len(unique_emps),
            date_range=date_range,
            issue_count=issue_count,
            new_emp_count=new_emp_count,
        )
        self.import_btn.configure(state="normal")
        self.cancel_btn.configure(state="normal")

    def _on_cancel(self):
        self._pending_path = None
        self._pending_rows = []
        self._render_preview_placeholder()
        self.import_btn.configure(state="disabled")
        self.cancel_btn.configure(state="disabled")

    def _on_confirm(self):
        if not self._pending_rows:
            return

        # Auto-detect mode month from imported dates
        months = [r.tanggal[:7] for r in self._pending_rows if r.tanggal]
        mode_month = Counter(months).most_common(1)[0][0] if months else None

        with get_connection(DB_PATH) as conn:
            for r in self._pending_rows:
                emp_id = upsert_employee(
                    conn, no_staff=r.no_staff, nama=r.nama, dept=r.dept
                )
                upsert_attendance(
                    conn, employee_id=emp_id, tanggal=r.tanggal,
                    hari=r.hari, tipe=r.tipe, jadwal=r.jadwal,
                    masuk=r.masuk, keluar=r.keluar,
                    kerja_jam=r.kerja_jam, lembur_jam=r.lembur_jam,
                    terlambat_menit=r.terlambat_menit,
                    has_issue=1 if is_issue(r) else 0,
                    imported_from=r.source_file,
                )
            if mode_month:
                set_setting(conn, "current_month", mode_month)

        row_count = len(self._pending_rows)
        month_display = _format_month_id(mode_month) if mode_month else "-"

        # Reset UI state before showing toast (so the toast is the last interaction)
        self.import_btn.configure(state="disabled")
        self.cancel_btn.configure(state="disabled")
        self._pending_rows = []
        self._pending_path = None
        self._render_preview_placeholder()

        show_success_toast(
            self.winfo_toplevel(),
            title="Impor Berhasil",
            message=(
                f"{row_count} baris fingerprint berhasil diimpor.\n"
                f"Bulan aktif diset ke {month_display}."
            ),
        )
