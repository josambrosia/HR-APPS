import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox
import customtkinter as ctk

from src.config import DB_PATH
from src.db.connection import get_connection
from src.core.session_state import notify_data_changed
from src.db.employees import upsert_employee, get_employee_by_no_staff
from src.db.attendance import upsert_attendance, list_recent_imports, count_overlap
from src.db.holidays import restamp_holidays
from src.db.settings import set_setting, get_setting
from src.parsers.fingerprint import parse_fingerprint_file
from src.core.issue_detector import is_issue
from src.ui.components.kpi_card import KPICard
from src.ui.components.progress_modal import ProgressModal
from src.ui.components.toast import show_success_toast
from src.ui.theme import (
    FONT_FAMILY,
    COLOR_BG, COLOR_SURFACE, COLOR_SURFACE_HIGH,
    COLOR_BORDER, COLOR_BORDER_STRONG,
    COLOR_ACCENT, COLOR_ACCENT_HOVER,
    COLOR_INFO, COLOR_WARN,
    COLOR_TEXT, COLOR_TEXT_DIM, COLOR_TEXT_MUTED,
    FONT_DISPLAY, FONT_SUBHEAD,
    FONT_BODY, FONT_BODY_BOLD, FONT_SMALL, FONT_LABEL,
    FONT_MONO_DATA, FONT_MONO_SMALL,
    SPACE_XS, SPACE_SM, SPACE_MD, SPACE_LG,
    RADIUS_SM, RADIUS_MD, RADIUS_LG,
)


_MONTH_ID = {
    1: "Januari", 2: "Februari", 3: "Maret", 4: "April",
    5: "Mei", 6: "Juni", 7: "Juli", 8: "Agustus",
    9: "September", 10: "Oktober", 11: "November", 12: "Desember",
}
_MONTH_ID_SHORT = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr",
    5: "Mei", 6: "Jun", 7: "Jul", 8: "Ags",
    9: "Sep", 10: "Okt", 11: "Nov", 12: "Des",
}


def _format_month_id(month_str: str) -> str:
    """'2026-04' → 'April 2026'. Falls back to the raw string if unparseable."""
    try:
        year_s, m_s = month_str.split("-")
        return f"{_MONTH_ID[int(m_s)]} {year_s}"
    except (ValueError, KeyError):
        return month_str


def _format_short_range(start_iso: str, end_iso: str) -> str:
    """Compact Indonesian date range:
        same month/year → '22 → 28 Apr 2026'
        different month, same year → '30 Apr → 5 Mei 2026'
        different year → '30 Des 2025 → 5 Jan 2026'
    """
    try:
        s = datetime.strptime(start_iso, "%Y-%m-%d")
        e = datetime.strptime(end_iso, "%Y-%m-%d")
    except ValueError:
        return f"{start_iso} → {end_iso}"
    if s.year != e.year:
        return f"{s.day} {_MONTH_ID_SHORT[s.month]} {s.year} → {e.day} {_MONTH_ID_SHORT[e.month]} {e.year}"
    if s.month != e.month:
        return f"{s.day} {_MONTH_ID_SHORT[s.month]} → {e.day} {_MONTH_ID_SHORT[e.month]} {e.year}"
    return f"{s.day} → {e.day} {_MONTH_ID_SHORT[e.month]} {e.year}"


def _format_relative_time(iso_dt: str) -> str:
    """ISO datetime to 'Hari ini HH:MM' / 'Kemarin HH:MM' / 'MMM D HH:MM'.

    Handles both ISO-UTC ('2026-05-13T08:19:47+00:00') and naive local
    ('2026-05-13 08:19:47') formats — falls back to raw if unparseable.
    """
    if not iso_dt:
        return "—"
    # Try ISO format with timezone first
    dt = None
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S"):
        try:
            dt = datetime.strptime(iso_dt, fmt)
            break
        except (ValueError, TypeError):
            continue
    if dt is None:
        return iso_dt
    # Strip timezone for local comparison (display-only)
    if dt.tzinfo is not None:
        dt = dt.astimezone().replace(tzinfo=None)
    now = datetime.now()
    today = now.date()
    if dt.date() == today:
        return f"Hari ini {dt.strftime('%H:%M')}"
    delta = today - dt.date()
    if delta.days == 1:
        return f"Kemarin {dt.strftime('%H:%M')}"
    return f"{_MONTH_ID_SHORT[dt.month]} {dt.day} {dt.strftime('%H:%M')}"


class ImportScreen(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self._pending_paths: list = []
        self._pending_rows: list = []
        self._build()

    def _build(self):
        # Header
        ctk.CTkLabel(
            self, text="Import Fingerprint",
            font=FONT_DISPLAY, text_color=COLOR_TEXT,
        ).pack(anchor="w", pady=(0, SPACE_LG))

        # ── Active month banner ──
        self.banner = ctk.CTkFrame(
            self, fg_color="#08222B",  # cyan 8% on dark
            border_width=1, border_color="#12454F",
            corner_radius=RADIUS_MD,
        )
        self.banner.pack(fill="x", pady=(0, SPACE_MD))
        self.banner_icon = ctk.CTkLabel(
            self.banner, text="📆",
            font=(FONT_FAMILY, 16),
            text_color=COLOR_INFO,
        )
        self.banner_icon.pack(side="left", padx=(SPACE_MD, SPACE_SM), pady=SPACE_SM)
        self.banner_text = ctk.CTkLabel(
            self.banner, text="",
            font=FONT_BODY,
            text_color=COLOR_TEXT,
            anchor="w", justify="left",
        )
        self.banner_text.pack(side="left", fill="x", expand=True, pady=SPACE_SM)
        self._update_banner()

        # ── Drop zone (shown only when no file pending) ──
        self.dropzone = self._build_dropzone()
        self.dropzone.pack(fill="x", pady=(0, SPACE_LG))

        # ── File chip (shown only when file pending, hidden initially) ──
        self.chip_frame = ctk.CTkFrame(
            self, fg_color=COLOR_SURFACE,
            border_width=1, border_color=COLOR_BORDER,
            corner_radius=RADIUS_MD,
        )
        # Don't pack yet — populated by _show_chip()

        # ── Preview cards (populated after file pick) ──
        self.preview_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.preview_frame.pack(fill="x", pady=(0, SPACE_LG))
        self._render_preview_placeholder()

        # ── History list (always shown at bottom) ──
        self.history_frame = ctk.CTkFrame(
            self, fg_color=COLOR_SURFACE,
            border_width=1, border_color=COLOR_BORDER,
            corner_radius=RADIUS_MD,
        )
        self.history_frame.pack(fill="x", pady=(SPACE_LG, 0))
        self._render_history()

    def _build_dropzone(self):
        """Build the large drop zone shown when no file is pending."""
        zone = ctk.CTkFrame(
            self,
            fg_color="#0F0F0F",
            border_width=2,
            border_color=COLOR_BORDER_STRONG,
            corner_radius=RADIUS_LG,
            height=200,
        )
        zone.pack_propagate(False)

        inner = ctk.CTkFrame(zone, fg_color="transparent")
        inner.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(
            inner, text="📥",
            font=(FONT_FAMILY, 28),
            text_color=COLOR_TEXT,
        ).pack()
        ctk.CTkLabel(
            inner, text="Pilih file fingerprint .xls",
            font=FONT_SUBHEAD, text_color=COLOR_TEXT,
        ).pack(pady=(SPACE_SM, SPACE_XS))
        ctk.CTkLabel(
            inner, text="klik tombol di bawah untuk browse",
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

        # Hover state — nested counter prevents flicker when crossing children
        self._dropzone_pointer_inside = 0

        def _on_enter(_e):
            self._dropzone_pointer_inside += 1
            if self._dropzone_pointer_inside > 0:
                zone.configure(border_color=COLOR_ACCENT)

        def _on_leave(_e):
            self._dropzone_pointer_inside -= 1
            if self._dropzone_pointer_inside <= 0:
                self._dropzone_pointer_inside = 0
                zone.configure(border_color=COLOR_BORDER_STRONG)

        def _bind_hover_recursive(widget):
            widget.bind("<Enter>", _on_enter, add="+")
            widget.bind("<Leave>", _on_leave, add="+")
            for child in widget.winfo_children():
                _bind_hover_recursive(child)

        _bind_hover_recursive(zone)

        # NOTE: OS-level drag-and-drop was removed (v10). It required ctypes
        # WNDPROC subclassing (windnd / in-house dnd_hook), which proved
        # catastrophically fragile — a single ctypes marshalling slip
        # (buffer-size in windnd, pointer truncation in the rewrite) crashes
        # the WHOLE app via Win32 __fastfail, bypassing Python exception
        # handling. Blast radius is unacceptable for a nice-to-have. The
        # zone stays fully functional via the "📁 Browse File" button.

        return zone

    def _show_chip(self, filename: str, size_kb: int, parse_ms: int):
        """Replace drop zone with file chip (file selected state).

        Label derives from self._pending_paths: 'FILES TERPILIH (N files)'
        when multi-file, else 'FILE TERPILIH'.
        """
        self.dropzone.pack_forget()

        for w in self.chip_frame.winfo_children():
            w.destroy()

        icon = ctk.CTkLabel(
            self.chip_frame, text="📄",
            font=(FONT_FAMILY, 24),
            text_color=COLOR_TEXT,
        )
        icon.pack(side="left", padx=(SPACE_MD, SPACE_SM), pady=SPACE_MD)

        info = ctk.CTkFrame(self.chip_frame, fg_color="transparent")
        info.pack(side="left", fill="x", expand=True, pady=SPACE_MD)
        is_multi = len(self._pending_paths) > 1
        label_text = (
            f"FILES TERPILIH ({len(self._pending_paths)} files)"
            if is_multi else "FILE TERPILIH"
        )
        ctk.CTkLabel(
            info, text=label_text,
            font=FONT_LABEL, text_color=COLOR_TEXT_MUTED,
            anchor="w",
        ).pack(fill="x")
        ctk.CTkLabel(
            info, text=filename,
            font=FONT_MONO_DATA, text_color=COLOR_TEXT,
            anchor="w",
        ).pack(fill="x")
        ctk.CTkLabel(
            info, text=f"{size_kb} KB · diparsing dalam {parse_ms} ms",
            font=FONT_MONO_SMALL, text_color=COLOR_TEXT_MUTED,
            anchor="w",
        ).pack(fill="x")

        actions = ctk.CTkFrame(self.chip_frame, fg_color="transparent")
        actions.pack(side="right", padx=SPACE_MD, pady=SPACE_MD)
        ctk.CTkButton(
            actions, text="↻ Ganti",
            command=self._on_pick_file,
            fg_color="transparent",
            border_width=1, border_color=COLOR_BORDER_STRONG,
            text_color=COLOR_TEXT_DIM,
            hover_color=COLOR_SURFACE_HIGH,
            font=FONT_BODY_BOLD,
            width=80,
        ).pack(side="left", padx=(0, SPACE_XS))
        ctk.CTkButton(
            actions, text="✕ Batal",
            command=self._on_cancel,
            fg_color="transparent",
            border_width=1, border_color=COLOR_BORDER_STRONG,
            text_color=COLOR_TEXT_DIM,
            hover_color=COLOR_SURFACE_HIGH,
            font=FONT_BODY_BOLD,
            width=80,
        ).pack(side="left", padx=(0, SPACE_XS))
        ctk.CTkButton(
            actions, text="✓ Konfirmasi",
            command=self._on_confirm,
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
            text_color=COLOR_BG,
            font=FONT_BODY_BOLD,
            width=120,
        ).pack(side="left")

        self.chip_frame.pack(fill="x", pady=(0, SPACE_MD), before=self.preview_frame)

    def _hide_chip(self):
        """Return to no-file-pending state — drop zone visible, chip hidden."""
        self.chip_frame.pack_forget()
        # Re-pack dropzone before preview_frame so it lands above the (now placeholder) preview.
        # before= is needed here because pack() defaults to appending at end of slave list.
        self.dropzone.pack(fill="x", pady=(0, SPACE_LG), before=self.preview_frame)

    def _update_banner(self):
        """Refresh banner based on current state (active month + pending file)."""
        with get_connection(DB_PATH) as conn:
            current = get_setting(conn, "current_month") or ""
        current_display = _format_month_id(current) if current else "(belum ada bulan aktif)"

        if self._pending_rows:
            months = [r.tanggal[:7] for r in self._pending_rows if r.tanggal]
            if months:
                pending_month = Counter(months).most_common(1)[0][0]
                if current and pending_month != current:
                    # ROSE warning state
                    self.banner.configure(
                        fg_color="#2A0A14",
                        border_color="#5C1E2A",
                    )
                    self.banner_icon.configure(text="⚠", text_color=COLOR_WARN)
                    self.banner_text.configure(
                        text=(
                            f"Bulan aktif akan diubah: "
                            f"{current_display} → {_format_month_id(pending_month)} setelah konfirmasi impor."
                        ),
                    )
                    return
        # Default: CYAN info state
        self.banner.configure(
            fg_color="#08222B",
            border_color="#12454F",
        )
        self.banner_icon.configure(text="📆", text_color=COLOR_INFO)
        self.banner_text.configure(
            text=(
                f"Bulan aktif saat ini: {current_display}. "
                f"File baru akan auto-detect bulan dan update jika berbeda."
            ),
        )

    def _render_history(self):
        """Render the 'Riwayat Import Terakhir' list at the bottom."""
        for w in self.history_frame.winfo_children():
            w.destroy()

        ctk.CTkLabel(
            self.history_frame, text="RIWAYAT IMPORT TERAKHIR",
            font=FONT_LABEL, text_color=COLOR_TEXT_MUTED,
            anchor="w",
        ).pack(fill="x", padx=SPACE_MD, pady=(SPACE_SM, SPACE_XS))

        with get_connection(DB_PATH) as conn:
            items = list_recent_imports(conn, limit=5)

        if not items:
            ctk.CTkLabel(
                self.history_frame, text="(belum ada riwayat impor)",
                font=FONT_BODY, text_color=COLOR_TEXT_MUTED,
                anchor="w",
            ).pack(fill="x", padx=SPACE_MD, pady=(0, SPACE_SM))
            return

        for it in items:
            row = ctk.CTkFrame(self.history_frame, fg_color="transparent")
            row.pack(fill="x", padx=SPACE_MD, pady=2)
            ctk.CTkLabel(
                row, text=_format_relative_time(it["imported_at"]),
                font=FONT_MONO_SMALL, text_color=COLOR_TEXT_MUTED,
                anchor="w", width=120,
            ).pack(side="left")
            ctk.CTkLabel(
                row, text=it["imported_from"],
                font=FONT_MONO_DATA, text_color=COLOR_TEXT,
                anchor="w",
            ).pack(side="left", fill="x", expand=True, padx=(SPACE_SM, SPACE_SM))
            ctk.CTkLabel(
                row, text=f"✓ {it['emp_count']} emp",
                font=FONT_MONO_SMALL, text_color=COLOR_TEXT_DIM,
                fg_color="#0F2218",
                corner_radius=RADIUS_SM,
                anchor="e", width=70,
            ).pack(side="right")
        ctk.CTkFrame(self.history_frame, fg_color="transparent", height=SPACE_SM).pack()

    def _render_preview_placeholder(self):
        """Empty-state placeholder before file selection."""
        for child in self.preview_frame.winfo_children():
            child.destroy()
        ctk.CTkLabel(
            self.preview_frame, text="(belum ada file dipilih)",
            font=FONT_BODY, text_color=COLOR_TEXT_MUTED,
        ).pack(anchor="w", pady=SPACE_SM)

    def _render_preview_cards(self, pegawai_count: int, date_range: str,
                              issue_count: int, new_emp_count: int,
                              overwrite_count: int = 0):
        """Render the 5 preview metric cards in a grid."""
        for child in self.preview_frame.winfo_children():
            child.destroy()

        for i in range(5):
            self.preview_frame.grid_columnconfigure(i, weight=1)

        overwrite_color = COLOR_WARN if overwrite_count > 0 else COLOR_TEXT_MUTED
        cards = [
            ("Pegawai", str(pegawai_count), COLOR_TEXT, True, None),
            ("Range Tanggal", date_range, COLOR_INFO, False, FONT_BODY_BOLD),
            ("Issue Baru", str(issue_count), COLOR_WARN, True, None),
            ("Pegawai Baru", str(new_emp_count), COLOR_INFO, True, None),
            ("Akan Menimpa", str(overwrite_count), overwrite_color, True, None),
        ]
        for col, (label, value, value_color, mono, value_font) in enumerate(cards):
            KPICard(
                self.preview_frame, label, value,
                value_color=value_color, mono=mono, value_font=value_font,
            ).grid(row=0, column=col, sticky="nsew", padx=SPACE_XS, pady=0)

        # Footnote when overwrite > 0
        if overwrite_count > 0:
            footnote = ctk.CTkLabel(
                self.preview_frame,
                text="* Alasan ijin yang sudah diinput tidak akan terhapus.",
                font=FONT_MONO_SMALL, text_color=COLOR_TEXT_MUTED,
                anchor="w",
            )
            footnote.grid(row=1, column=0, columnspan=5, sticky="w", pady=(SPACE_XS, 0))

    def _on_pick_file(self):
        """Open file dialog (multi-select OK), parse all, render preview + chip."""
        with get_connection(DB_PATH) as conn:
            initialdir = get_setting(conn, "last_import_folder") or str(Path.home() / "Documents")

        paths_tuple = filedialog.askopenfilenames(
            title="Pilih file fingerprint (boleh multi-select)",
            initialdir=initialdir,
            filetypes=[("Excel", "*.xls *.xlsx"), ("All files", "*.*")],
        )
        if not paths_tuple:
            return
        paths = [Path(p) for p in paths_tuple]
        self._ingest_paths(paths, source="dipilih")

    def _ingest_paths(self, paths: list, source: str = "dipilih") -> None:
        """Parse + render chip + preview cards for a list of file paths.

        Called by _on_pick_file (file dialog). Persists last folder, parses
        all files, computes metrics, renders chip + preview + banner.

        source: word inserted into multi-file label (currently always
            "dipilih") to give visual feedback about how files arrived.
        """
        with get_connection(DB_PATH) as conn:
            set_setting(conn, "last_import_folder", str(paths[0].parent))

        t0 = time.perf_counter()
        all_rows = []
        try:
            for p in paths:
                all_rows.extend(parse_fingerprint_file(p))
        except Exception as e:
            messagebox.showerror("Error parsing", str(e))
            self._pending_paths = []
            self._pending_rows = []
            return
        parse_ms = int((time.perf_counter() - t0) * 1000)

        if not all_rows:
            messagebox.showwarning(
                "File kosong",
                "Tidak ada baris yang bisa diimpor dari file yang dipilih.",
            )
            self._pending_paths = []
            self._pending_rows = []
            return

        self._pending_paths = paths
        self._pending_rows = all_rows

        issue_count = sum(1 for r in self._pending_rows if is_issue(r))
        unique_emps = {r.no_staff for r in self._pending_rows}
        dates = sorted({r.tanggal for r in self._pending_rows})
        date_range = _format_short_range(dates[0], dates[-1]) if dates else "(empty)"

        new_emp_count = 0
        with get_connection(DB_PATH) as conn:
            for no_staff in unique_emps:
                if get_employee_by_no_staff(conn, no_staff) is None:
                    new_emp_count += 1
            overlap = count_overlap(conn, self._pending_rows)

        if len(paths) == 1:
            filename = paths[0].name
            size_kb = paths[0].stat().st_size // 1024
        else:
            filename = f"{len(paths)} file {source}"
            size_kb = sum(p.stat().st_size for p in paths) // 1024

        self._show_chip(filename, size_kb, parse_ms)
        self._render_preview_cards(
            pegawai_count=len(unique_emps),
            date_range=date_range,
            issue_count=issue_count,
            new_emp_count=new_emp_count,
            overwrite_count=overlap["overwrite"],
        )
        self._update_banner()

    def _on_cancel(self):
        self._pending_paths = []
        self._pending_rows = []
        self._hide_chip()
        self._render_preview_placeholder()
        # history unchanged — cancel doesn't write to DB
        self._update_banner()

    def _on_confirm(self):
        if not self._pending_rows:
            return

        months = [r.tanggal[:7] for r in self._pending_rows if r.tanggal]
        mode_month = Counter(months).most_common(1)[0][0] if months else None

        total_rows = len(self._pending_rows)
        use_progress = total_rows > 50

        if use_progress:
            cm = ProgressModal(self.winfo_toplevel(), title="Memproses Import")
        else:
            from contextlib import nullcontext
            cm = nullcontext()

        with cm as progress, get_connection(DB_PATH) as conn:
            if use_progress:
                progress.update_progress(0.0, f"Inserting {total_rows} rows...")
            for i, r in enumerate(self._pending_rows):
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
                if use_progress and (i + 1) % 10 == 0:
                    progress.update_progress(
                        (i + 1) / total_rows,
                        f"Inserting row {i+1}/{total_rows}...",
                    )
            if mode_month:
                set_setting(conn, "current_month", mode_month)

            # Re-stamp holiday status: upsert_attendance overwrites tipe back
            # to 'Hari Kerja', so re-apply 'Hari Libur' + auto-resolve for
            # dates in the holidays table (see Hari Libur design spec).
            restamp_holidays(conn)

        notify_data_changed()
        row_count = len(self._pending_rows)
        month_display = _format_month_id(mode_month) if mode_month else "-"

        self._pending_rows = []
        self._pending_paths = []
        self._hide_chip()
        self._render_preview_placeholder()
        self._update_banner()
        self._render_history()

        show_success_toast(
            self.winfo_toplevel(),
            title="Impor Berhasil",
            message=(
                f"{row_count} baris fingerprint berhasil diimpor.\n"
                f"Bulan aktif diset ke {month_display}."
            ),
        )
