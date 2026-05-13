import os
from pathlib import Path
from tkinter import filedialog, messagebox
import customtkinter as ctk

from src.config import DB_PATH
from src.db.connection import get_connection
from src.db.settings import get_setting, set_setting
from src.db.export_history import record_export, list_recent_exports
from src.core.report_filler import fill_monthly_report
from src.core.week_utils import full_month_range
from src.ui.components.kpi_card import KPICard
from src.ui.screens.import_screen import _format_month_id, _format_relative_time
from src.ui.theme import (
    FONT_FAMILY,
    COLOR_BG, COLOR_SURFACE, COLOR_SURFACE_HIGH,
    COLOR_BORDER, COLOR_BORDER_STRONG,
    COLOR_ACCENT, COLOR_ACCENT_HOVER,
    COLOR_INFO, COLOR_SUCCESS, COLOR_WARN,
    COLOR_TEXT, COLOR_TEXT_DIM, COLOR_TEXT_MUTED, COLOR_TEXT_DISABLED,
    FONT_DISPLAY,
    FONT_BODY, FONT_BODY_BOLD, FONT_LABEL,
    FONT_MONO_DATA, FONT_MONO_SMALL,
    SPACE_XS, SPACE_SM, SPACE_MD, SPACE_LG,
    RADIUS_SM, RADIUS_MD,
)


class ExportScreen(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self._selected: Path | None = None
        self._build()

    def _build(self):
        # Header
        ctk.CTkLabel(
            self, text="Export Laporan Bulanan",
            font=FONT_DISPLAY, text_color=COLOR_TEXT,
        ).pack(anchor="w", pady=(0, SPACE_LG))

        # ── Active month banner ──
        self.banner = ctk.CTkFrame(
            self, fg_color="#08222B",  # cyan tint
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

        # ── Picker zone (initial state) ──
        self.picker_zone = self._build_picker_zone()
        self.picker_zone.pack(fill="x", pady=(0, SPACE_LG))

        # ── File chip (shown after pick) ──
        self.chip_frame = ctk.CTkFrame(
            self, fg_color=COLOR_SURFACE,
            border_width=1, border_color=COLOR_BORDER,
            corner_radius=RADIUS_MD,
        )
        # Not packed initially

        # ── Preview cards (after dry-run) ──
        self.preview_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.preview_frame.pack(fill="x", pady=(0, SPACE_LG))
        self._render_preview_placeholder()

        # ── Result strip (after successful export) ──
        self.result_frame = ctk.CTkFrame(self, fg_color="transparent")
        # Not packed initially

        # ── History list at bottom ──
        self.history_frame = ctk.CTkFrame(
            self, fg_color=COLOR_SURFACE,
            border_width=1, border_color=COLOR_BORDER,
            corner_radius=RADIUS_MD,
        )
        self.history_frame.pack(fill="x", pady=(SPACE_LG, 0))
        self._render_history()

    def _build_picker_zone(self):
        """Build the picker card shown when no template selected."""
        zone = ctk.CTkFrame(
            self, fg_color=COLOR_SURFACE,
            border_width=1, border_color=COLOR_BORDER,
            corner_radius=RADIUS_MD,
        )
        ctk.CTkLabel(
            zone, text="TEMPLATE LAPORAN BULANAN",
            font=FONT_LABEL, text_color=COLOR_TEXT_MUTED,
        ).pack(anchor="w", padx=SPACE_LG, pady=(SPACE_MD, SPACE_XS))

        row = ctk.CTkFrame(zone, fg_color="transparent")
        row.pack(fill="x", padx=SPACE_LG, pady=(0, SPACE_MD))
        ctk.CTkLabel(
            row, text="(belum ada template dipilih)",
            font=FONT_MONO_DATA, text_color=COLOR_TEXT_MUTED,
            anchor="w",
        ).pack(side="left", fill="x", expand=True)
        ctk.CTkButton(
            row, text="📁 Browse",
            command=self._pick,
            fg_color="transparent",
            border_width=1, border_color=COLOR_INFO,
            text_color=COLOR_INFO,
            hover_color=COLOR_SURFACE_HIGH,
            font=FONT_BODY_BOLD,
            width=120,
        ).pack(side="right", padx=(SPACE_SM, 0))
        return zone

    def _show_chip(self, template_path: Path, predicted_out_name: str = None):
        """Replace picker zone with file chip + inline action buttons.

        predicted_out_name: filename string to show in "Akan menyimpan sebagai".
            Comes from fill_monthly_report's dry-run out_path.name — using this
            instead of computing locally keeps both sides in sync if the naming
            convention ever changes.
        """
        self.picker_zone.pack_forget()
        self.result_frame.pack_forget()

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
        ctk.CTkLabel(
            info, text="TEMPLATE LAPORAN BULANAN",
            font=FONT_LABEL, text_color=COLOR_TEXT_MUTED,
            anchor="w",
        ).pack(fill="x")
        ctk.CTkLabel(
            info, text=template_path.name,
            font=FONT_MONO_DATA, text_color=COLOR_TEXT,
            anchor="w",
        ).pack(fill="x")
        size_kb = template_path.stat().st_size // 1024
        ctk.CTkLabel(
            info, text=f"{template_path.parent} · {size_kb} KB",
            font=FONT_MONO_SMALL, text_color=COLOR_TEXT_MUTED,
            anchor="w",
        ).pack(fill="x")
        display_name = predicted_out_name or template_path.name  # fallback to template name
        ctk.CTkLabel(
            info, text=f"→ Akan menyimpan sebagai: {display_name}",
            font=FONT_MONO_SMALL, text_color=COLOR_TEXT_DISABLED,
            anchor="w",
        ).pack(fill="x", pady=(SPACE_XS, 0))

        actions = ctk.CTkFrame(self.chip_frame, fg_color="transparent")
        actions.pack(side="right", padx=SPACE_MD, pady=SPACE_MD)
        ctk.CTkButton(
            actions, text="↻ Ganti",
            command=self._pick,
            fg_color="transparent",
            border_width=1, border_color=COLOR_BORDER_STRONG,
            text_color=COLOR_TEXT_DIM,
            hover_color=COLOR_SURFACE_HIGH,
            font=FONT_BODY_BOLD,
            width=80,
        ).pack(side="left", padx=(0, SPACE_XS))
        ctk.CTkButton(
            actions, text="💾 Export",
            command=self._do_export,
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
            text_color=COLOR_BG,
            font=FONT_BODY_BOLD,
            width=110,
        ).pack(side="left")

        self.chip_frame.pack(fill="x", pady=(0, SPACE_MD), before=self.preview_frame)

    def _update_banner(self):
        """Refresh banner with current_month info + data summary."""
        with get_connection(DB_PATH) as conn:
            current = get_setting(conn, "current_month") or ""
            emp = issues = unresolved = 0
            if current:
                start, end = full_month_range(current)
                row = conn.execute("""
                    SELECT
                        COUNT(DISTINCT employee_id) AS emp_count,
                        SUM(CASE WHEN has_issue = 1 THEN 1 ELSE 0 END) AS issue_count,
                        SUM(CASE WHEN has_issue = 1 AND reason_category IS NULL THEN 1 ELSE 0 END) AS unresolved_count
                    FROM attendance_records
                    WHERE tanggal BETWEEN ? AND ?
                """, (start, end)).fetchone()
                if row:
                    emp = row["emp_count"] or 0
                    issues = row["issue_count"] or 0
                    unresolved = row["unresolved_count"] or 0
        if current:
            self.banner.configure(fg_color="#08222B", border_color="#12454F")
            self.banner_icon.configure(text="📆", text_color=COLOR_INFO)
            self.banner_text.configure(
                text=(
                    f"Akan mengisi laporan untuk: {_format_month_id(current)}\n"
                    f"{emp} pegawai · {issues} issues · {unresolved} unresolved"
                ),
            )
        else:
            self.banner.configure(fg_color="#2A0A14", border_color="#5C1E2A")
            self.banner_icon.configure(text="⚠", text_color=COLOR_WARN)
            self.banner_text.configure(
                text="Belum ada bulan aktif — pilih di Active Month dulu.",
            )

    def _render_preview_placeholder(self):
        for child in self.preview_frame.winfo_children():
            child.destroy()
        ctk.CTkLabel(
            self.preview_frame, text="(pilih template untuk preview match)",
            font=FONT_BODY, text_color=COLOR_TEXT_MUTED,
        ).pack(anchor="w", pady=SPACE_SM)

    def _render_preview_cards(self, filled: int, na: int, not_found: int):
        """Render 3 dry-run preview cards: Akan terisi / NA / Tidak ditemukan."""
        for child in self.preview_frame.winfo_children():
            child.destroy()

        for i in range(3):
            self.preview_frame.grid_columnconfigure(i, weight=1)

        cards = [
            ("Akan terisi", str(filled), COLOR_SUCCESS),
            ("NA / Belum kabar", str(na), COLOR_WARN),
            ("Tidak ditemukan", str(not_found), COLOR_WARN if not_found > 0 else COLOR_TEXT_MUTED),
        ]
        for col, (label, value, value_color) in enumerate(cards):
            KPICard(
                self.preview_frame, label, value,
                value_color=value_color, mono=True,
            ).grid(row=0, column=col, sticky="nsew", padx=SPACE_XS, pady=0)

    def _render_result_strip(self, out_path: Path, summary):
        """Show emerald-bordered success strip with Folder/Open buttons."""
        for w in self.result_frame.winfo_children():
            w.destroy()

        strip = ctk.CTkFrame(
            self.result_frame,
            fg_color="#0F2218",
            border_width=1, border_color="#1A4434",
            corner_radius=RADIUS_MD,
        )
        strip.pack(fill="x")

        icon = ctk.CTkLabel(
            strip, text="✓",
            font=(FONT_FAMILY, 22, "bold"),
            text_color=COLOR_SUCCESS,
        )
        icon.pack(side="left", padx=(SPACE_MD, SPACE_SM), pady=SPACE_MD)

        info = ctk.CTkFrame(strip, fg_color="transparent")
        info.pack(side="left", fill="x", expand=True, pady=SPACE_MD)
        ctk.CTkLabel(
            info, text="Sukses. File tersimpan sebagai:",
            font=FONT_BODY_BOLD, text_color=COLOR_TEXT,
            anchor="w",
        ).pack(fill="x")
        ctk.CTkLabel(
            info, text=out_path.name,
            font=FONT_MONO_DATA, text_color=COLOR_TEXT,
            anchor="w",
        ).pack(fill="x")
        ctk.CTkLabel(
            info,
            text=f"{summary.filled_count} terisi · {summary.na_count} NA · {summary.not_found_count} not found",
            font=FONT_MONO_SMALL, text_color=COLOR_TEXT_MUTED,
            anchor="w",
        ).pack(fill="x", pady=(SPACE_XS, 0))

        actions = ctk.CTkFrame(strip, fg_color="transparent")
        actions.pack(side="right", padx=SPACE_MD, pady=SPACE_MD)
        ctk.CTkButton(
            actions, text="📂 Folder",
            command=lambda: self._open_folder(out_path.parent),
            fg_color="transparent",
            border_width=1, border_color=COLOR_INFO,
            text_color=COLOR_INFO,
            hover_color=COLOR_SURFACE_HIGH,
            font=FONT_BODY_BOLD,
            width=90,
        ).pack(side="left", padx=(0, SPACE_XS))
        ctk.CTkButton(
            actions, text="📄 Open",
            command=lambda: self._open_file(out_path),
            fg_color="transparent",
            border_width=1, border_color=COLOR_INFO,
            text_color=COLOR_INFO,
            hover_color=COLOR_SURFACE_HIGH,
            font=FONT_BODY_BOLD,
            width=90,
        ).pack(side="left")

        self.result_frame.pack(fill="x", pady=(0, SPACE_LG), before=self.history_frame)

    def _open_folder(self, folder: Path):
        try:
            os.startfile(str(folder))
        except Exception as e:
            messagebox.showwarning("Tidak bisa buka folder", str(e))

    def _open_file(self, file_path: Path):
        try:
            os.startfile(str(file_path))
        except Exception as e:
            messagebox.showwarning("Tidak bisa buka file", str(e))

    def _render_history(self):
        """Render the 'Riwayat Export Terakhir' list at the bottom."""
        for w in self.history_frame.winfo_children():
            w.destroy()

        ctk.CTkLabel(
            self.history_frame, text="RIWAYAT EXPORT TERAKHIR",
            font=FONT_LABEL, text_color=COLOR_TEXT_MUTED,
            anchor="w",
        ).pack(fill="x", padx=SPACE_MD, pady=(SPACE_SM, SPACE_XS))

        with get_connection(DB_PATH) as conn:
            items = list_recent_exports(conn, limit=5)

        if not items:
            ctk.CTkLabel(
                self.history_frame, text="(belum ada riwayat export)",
                font=FONT_BODY, text_color=COLOR_TEXT_MUTED,
                anchor="w",
            ).pack(fill="x", padx=SPACE_MD, pady=(0, SPACE_SM))
            return

        for it in items:
            row = ctk.CTkFrame(self.history_frame, fg_color="transparent")
            row.pack(fill="x", padx=SPACE_MD, pady=2)
            ctk.CTkLabel(
                row, text=_format_relative_time(it["created_at"]),
                font=FONT_MONO_SMALL, text_color=COLOR_TEXT_MUTED,
                anchor="w", width=120,
            ).pack(side="left")
            ctk.CTkLabel(
                row, text=Path(it["out_path"]).name,
                font=FONT_MONO_DATA, text_color=COLOR_TEXT,
                anchor="w",
            ).pack(side="left", fill="x", expand=True, padx=(SPACE_SM, SPACE_SM))
            total = it["filled"] + it["na"] + it["not_found"]
            is_full = it["na"] == 0 and it["not_found"] == 0
            badge_text = f"✓ {it['filled']}/{total}" if is_full else f"{it['filled']}/{total}"
            badge_bg = "#0F2218" if is_full else "#22141A"
            badge_color = COLOR_SUCCESS if is_full else COLOR_WARN
            ctk.CTkLabel(
                row, text=badge_text,
                font=FONT_MONO_SMALL, text_color=badge_color,
                fg_color=badge_bg, corner_radius=RADIUS_SM,
                anchor="e", width=80,
            ).pack(side="right")
        ctk.CTkFrame(self.history_frame, fg_color="transparent", height=SPACE_SM).pack()

    def _pick(self):
        with get_connection(DB_PATH) as conn:
            initialdir = get_setting(conn, "last_export_template_folder") or str(Path.home() / "Documents")

        path = filedialog.askopenfilename(
            title="Pilih Laporan Bulanan",
            initialdir=initialdir,
            filetypes=[("Excel", "*.xlsx")],
        )
        if not path:
            return
        self._selected = Path(path)

        with get_connection(DB_PATH) as conn:
            set_setting(conn, "last_export_template_folder", str(self._selected.parent))

        # Run dry-run preview
        try:
            with get_connection(DB_PATH) as conn:
                out_path, summary = fill_monthly_report(
                    self._selected, conn, dry_run=True,
                )
        except Exception as e:
            messagebox.showerror("Error preview", str(e))
            self._selected = None
            return

        self._show_chip(self._selected, predicted_out_name=out_path.name)
        self._render_preview_cards(
            filled=summary.filled_count,
            na=summary.na_count,
            not_found=summary.not_found_count,
        )
        self._update_banner()

    def _do_export(self):
        if not self._selected:
            return
        try:
            with get_connection(DB_PATH) as conn:
                out_path, summary = fill_monthly_report(
                    self._selected, conn, dry_run=False,
                )
                ym = get_setting(conn, "current_month") or "?"
                record_export(
                    conn,
                    out_path=str(out_path),
                    template=str(self._selected),
                    year_month=ym,
                    filled=summary.filled_count,
                    na=summary.na_count,
                    not_found=summary.not_found_count,
                )
        except Exception as e:
            messagebox.showerror("Error export", str(e))
            return

        self._render_result_strip(out_path, summary)
        self._render_history()
