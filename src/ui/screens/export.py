import os
import tempfile
import time
from pathlib import Path
from tkinter import filedialog
import customtkinter as ctk

from src.config import DB_PATH
from src.db.connection import get_connection
from src.db.settings import get_setting, set_setting
from src.db.export_history import record_export, list_recent_exports
from src.core.report_filler import fill_monthly_report
from src.core.week_utils import full_month_range, weeks_in_month
from src.core.weekly_export import generate_weekly_export
from src.core.filename_parser import detect_year_month_from_filename
from src.core.report_generator import generate_monthly_report, month_label
from src.db.attendance import list_months_with_stats, count_summary_for_period
from src.ui import feedback
from src.ui.tasks import BusyGuard, run_bg
from src.ui.components.kpi_card import KPICard
from src.ui.components.toast import show_success_toast
from src.ui.components.active_month_banner import ActiveMonthBanner
from src.ui.components.file_chip import FileChip, FileChipAction
from src.ui.components.history_list import HistoryList, HistoryRow
from src.ui.screens.import_screen import _format_month_id, _format_relative_time
from src.ui.theme import (
    FONT_FAMILY,
    COLOR_BG, COLOR_SURFACE, COLOR_SURFACE_HIGH,
    COLOR_BORDER, COLOR_BORDER_STRONG,
    COLOR_ACCENT, COLOR_ACCENT_HOVER,
    COLOR_INFO, COLOR_SUCCESS, COLOR_WARN,
    COLOR_SUCCESS_TINT_BG, COLOR_SUCCESS_TINT_BORDER,
    COLOR_WARN_TINT_BADGE_BG,
    COLOR_TEXT, COLOR_TEXT_DIM, COLOR_TEXT_MUTED,
    FONT_DISPLAY,
    FONT_BODY, FONT_BODY_BOLD, FONT_LABEL, FONT_SMALL,
    FONT_MONO_DATA, FONT_MONO_SMALL,
    SPACE_XS, SPACE_SM, SPACE_MD, SPACE_LG,
    RADIUS_MD,
)

_KIND_LABELS = {
    "fill": "Isi Template",
    "generate_bulanan": "Generate Bulanan",
    "generate_mingguan": "Generate Mingguan",
}


# ── Worker bodies (run in a background thread via run_bg) ──────────────
# Module-level and Tk-free so tests can call them synchronously. Each one
# opens its OWN SQLite connection — get_connection() creates a fresh
# connection per use, the sanctioned cross-thread pattern (see the
# src/ui/tasks.py docstring). NEVER touch widgets from these functions.

def export_fill_work(db_path, template_path: Path, out_dir: Path):
    """Fill the Laporan Bulanan template + record export history.

    Returns (out_path, FillSummary).
    """
    with get_connection(db_path) as conn:
        out_path, summary = fill_monthly_report(
            template_path, conn, dry_run=False, out_dir=out_dir,
        )
        ym = get_setting(conn, "current_month") or "?"
        record_export(
            conn,
            out_path=str(out_path),
            template=str(template_path),
            year_month=ym,
            filled=summary.filled_count,
            na=summary.na_count,
            not_found=summary.not_found_count,
        )
    return out_path, summary


def preview_fill_work(db_path, template_path: Path, tmp_dir: Path) -> Path:
    """Fill the template into a temp dir (no history entry). Returns out_path."""
    tmp_dir.mkdir(parents=True, exist_ok=True)
    with get_connection(db_path) as conn:
        out_path, _summary = fill_monthly_report(
            template_path, conn, dry_run=False, out_dir=tmp_dir,
        )
    return out_path


def generate_bulanan_work(db_path, year_month: str, out_path: Path):
    """Generate Laporan Bulanan from DB + record history. Returns GenerateSummary."""
    with get_connection(db_path) as conn:
        summary = generate_monthly_report(
            conn, year_month=year_month, out_path=out_path,
        )
        record_export(
            conn, out_path=str(out_path), template="-",
            year_month=year_month, filled=summary.rows_generated,
            na=summary.na_count, not_found=0, kind="generate_bulanan",
        )
    return summary


def generate_mingguan_work(db_path, week_start: str, week_end: str, out_path: Path):
    """Generate Laporan Mingguan from DB + record history. Returns WeeklyExportSummary."""
    with get_connection(db_path) as conn:
        summary = generate_weekly_export(conn, week_start, week_end, out_path)
        record_export(
            conn, out_path=str(out_path), template="-",
            year_month=week_start[:7], filled=summary.rows, na=0,
            not_found=0, kind="generate_mingguan",
        )
    return summary


class ExportScreen(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self._selected: Path | None = None
        self._filename_mismatch = False
        self._detected_ym: str | None = None
        self._mode = "export"
        self._busy_guard: BusyGuard | None = None
        self._build_shell()

    def _build_shell(self):
        ctk.CTkLabel(
            self, text="Export", font=FONT_DISPLAY, text_color=COLOR_TEXT,
        ).pack(anchor="w", pady=(0, SPACE_MD))

        toggle = ctk.CTkFrame(self, fg_color="transparent")
        toggle.pack(anchor="w", pady=(0, SPACE_XS))
        self._mode_btns = {}
        for mode, label in (("export", "📤 Export"), ("generate", "⚙ Generate")):
            btn = ctk.CTkButton(
                toggle, text=label, width=150, height=32,
                command=lambda m=mode: self._show_mode(m),
                font=FONT_BODY_BOLD,
            )
            btn.pack(side="left", padx=(0, SPACE_XS))
            self._mode_btns[mode] = btn

        ctk.CTkLabel(
            self,
            text="Export = isi template dari atasan · Generate = buat file dari database",
            font=FONT_MONO_SMALL, text_color=COLOR_TEXT_MUTED,
        ).pack(anchor="w", pady=(0, SPACE_MD))

        self._export_panel = ctk.CTkFrame(self, fg_color="transparent")
        self._generate_panel = ctk.CTkFrame(self, fg_color="transparent")
        self._build_export_mode(self._export_panel)
        self._build_generate_mode(self._generate_panel)
        self._gen_built_sig = self._gen_signature()
        self._show_mode("export")

    def _gen_signature(self):
        """(active month, known months) the Generate panels were built
        from — their dropdown/week pills bake these in."""
        with get_connection(DB_PATH) as conn:
            months = tuple(r["year_month"] for r in list_months_with_stats(conn))
            active = get_setting(conn, "current_month") or ""
        return active, months

    def on_show(self):
        """Shell hook — cached re-display. The picked template/chip, mode,
        and preview survive (the point of caching); banner + history
        re-read the DB, and the Generate panels are rebuilt only when the
        active month / month list changed since they were built."""
        sig = self._gen_signature()
        if sig != self._gen_built_sig:
            self._gen_built_sig = sig
            for panel in (self._gen_bulanan_panel, self._gen_mingguan_panel):
                for child in panel.winfo_children():
                    child.destroy()
            self._build_gen_bulanan(self._gen_bulanan_panel)
            self._build_gen_mingguan(self._gen_mingguan_panel)
            self._show_gen_sub(self._gen_sub)
        self._update_banner()
        self._refresh_history()

    def _show_mode(self, mode):
        self._mode = mode
        for m, btn in self._mode_btns.items():
            if m == mode:
                btn.configure(
                    fg_color=COLOR_ACCENT, text_color=COLOR_BG,
                    hover_color=COLOR_ACCENT_HOVER,
                )
            else:
                btn.configure(
                    fg_color=COLOR_SURFACE, text_color=COLOR_TEXT_DIM,
                    hover_color=COLOR_SURFACE_HIGH,
                )
        self._export_panel.pack_forget()
        self._generate_panel.pack_forget()
        panel = self._export_panel if mode == "export" else self._generate_panel
        panel.pack(fill="both", expand=True)

    def _build_export_mode(self, parent):
        # ── Active month banner ──
        self.banner = ActiveMonthBanner(parent, variant="banner")
        self.banner.pack(fill="x", pady=(0, SPACE_MD))
        self._update_banner()

        # ── R8: Save Destination dropdown ──
        self.save_dest_frame = self._build_save_destination(parent)
        self.save_dest_frame.pack(fill="x", pady=(0, SPACE_MD))

        # ── Picker zone (initial state) ──
        self.picker_zone = self._build_picker_zone(parent)
        self.picker_zone.pack(fill="x", pady=(0, SPACE_LG))

        # ── File chip (shown after pick) ──
        self.chip = FileChip(parent)
        # Not packed initially

        # ── Preview cards (after dry-run) ──
        self.preview_frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.preview_frame.pack(fill="x", pady=(0, SPACE_LG))
        self._render_preview_placeholder()

        # ── Result strip (after successful export) ──
        self.result_frame = ctk.CTkFrame(parent, fg_color="transparent")
        # Not packed initially

        # ── History list at bottom ──
        self.history = HistoryList(
            parent, header="RIWAYAT EXPORT TERAKHIR",
            empty_text="(belum ada riwayat export)",
        )
        self.history.pack(fill="x", pady=(SPACE_LG, 0))
        self._refresh_history()

    def _build_picker_zone(self, parent):
        """Build the picker card shown when no template selected."""
        zone = ctk.CTkFrame(
            parent, fg_color=COLOR_SURFACE,
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

        size_kb = template_path.stat().st_size // 1024
        display_name = predicted_out_name or template_path.name  # fallback to template name
        self.chip.set_content(
            label="TEMPLATE LAPORAN BULANAN",
            filename=template_path.name,
            meta=f"{template_path.parent} · {size_kb} KB",
            extra=f"→ Akan menyimpan sebagai: {display_name}",
            actions=(
                FileChipAction("↻ Ganti", self._pick),
                FileChipAction("👁 Preview", self._preview_file, kind="info", width=100),
                FileChipAction("💾 Export", self._do_export, kind="primary", width=110),
            ),
        )
        # Fresh buttons after every set_content — keep refs so the busy
        # guard can freeze them and put "Memproses…" on the clicked one.
        (self._chip_ganti_btn,
         self._chip_preview_btn,
         self._chip_export_btn) = self.chip.action_buttons

        self.chip.pack(fill="x", pady=(0, SPACE_MD), before=self.preview_frame)

    def _update_banner(self):
        """Refresh banner with current_month info + data summary + R2 mismatch warn."""
        with get_connection(DB_PATH) as conn:
            current = get_setting(conn, "current_month") or ""
            emp = issues = unresolved = 0
            if current:
                start, end = full_month_range(current)
                stats = count_summary_for_period(conn, start, end)
                emp = stats["employees"]
                issues = stats["issues"]
                unresolved = stats["unresolved"]

        # R2 — filename mismatch state takes priority over standard cyan/rose
        mismatch = getattr(self, "_filename_mismatch", False)
        detected = getattr(self, "_detected_ym", None)
        if mismatch and detected:
            self.banner.set_warn(
                f"Mismatch: File mention '{_format_month_id(detected)}' "
                f"tapi bulan aktif '{_format_month_id(current)}'.\n"
                f"Data dari {_format_month_id(current)} akan dimasukkan ke template tersebut."
            )
            return

        if current:
            self.banner.set_info(
                f"Akan mengisi laporan untuk: {_format_month_id(current)}\n"
                f"{emp} pegawai · {issues} issues · {unresolved} unresolved"
            )
        else:
            self.banner.set_warn("Belum ada bulan aktif — pilih di Active Month dulu.")

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
            fg_color=COLOR_SUCCESS_TINT_BG,
            border_width=1, border_color=COLOR_SUCCESS_TINT_BORDER,
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

        self.result_frame.pack(fill="x", pady=(0, SPACE_LG), before=self.history)

    def _open_folder(self, folder: Path):
        try:
            os.startfile(str(folder))
        except Exception as e:
            feedback.show_warning(self, "Tidak bisa buka folder", str(e))

    def _open_file(self, file_path: Path):
        try:
            os.startfile(str(file_path))
        except Exception as e:
            feedback.show_warning(self, "Tidak bisa buka file", str(e))

    def _refresh_history(self):
        """Reload 'Riwayat Export Terakhir' rows from the DB."""
        with get_connection(DB_PATH) as conn:
            items = list_recent_exports(conn, limit=5)

        rows = []
        for it in items:
            total = it["filled"] + it["na"] + it["not_found"]
            is_full = it["na"] == 0 and it["not_found"] == 0
            kind = it.get("kind", "fill")
            rows.append(HistoryRow(
                time=_format_relative_time(it["created_at"]),
                title=Path(it["out_path"]).name,
                tag=_KIND_LABELS.get(kind, kind),
                badge_text=f"✓ {it['filled']}/{total}" if is_full else f"{it['filled']}/{total}",
                badge_color=COLOR_SUCCESS if is_full else COLOR_WARN,
                badge_bg=COLOR_SUCCESS_TINT_BG if is_full else COLOR_WARN_TINT_BADGE_BG,
                badge_width=80,
            ))
        self.history.set_rows(rows)

    def _build_save_destination(self, parent):
        """R8 — dropdown to choose where exported file is saved."""
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        ctk.CTkLabel(
            frame, text="SIMPAN OUTPUT KE",
            font=FONT_LABEL, text_color=COLOR_TEXT_MUTED,
        ).pack(anchor="w", padx=SPACE_XS)

        options = [
            "Folder template (default)",
            "Documents/HR Reports/",
            "Pilih folder lain...",
        ]
        self.save_dest_var = ctk.StringVar(value=options[0])

        # Restore from settings if previously set
        with get_connection(DB_PATH) as conn:
            mode = get_setting(conn, "export_save_mode") or "template_folder"
        mode_to_label = {
            "template_folder": options[0],
            "hr_reports": options[1],
            "custom": options[2],
        }
        self.save_dest_var.set(mode_to_label.get(mode, options[0]))

        self.save_dest_menu = ctk.CTkOptionMenu(
            frame,
            values=options,
            variable=self.save_dest_var,
            command=self._on_save_dest_change,
            fg_color=COLOR_SURFACE_HIGH,
            button_color=COLOR_BORDER,
            button_hover_color=COLOR_BORDER_STRONG,
            text_color=COLOR_TEXT,
            font=FONT_BODY,
            width=280,
        )
        self.save_dest_menu.pack(anchor="w", padx=SPACE_XS, pady=(SPACE_XS, 0))
        return frame

    def _on_save_dest_change(self, value: str):
        label_to_mode = {
            "Folder template (default)": "template_folder",
            "Documents/HR Reports/": "hr_reports",
            "Pilih folder lain...": "custom",
        }
        mode = label_to_mode.get(value, "template_folder")
        if mode == "custom":
            chosen = filedialog.askdirectory(title="Pilih folder save destination")
            if not chosen:
                # Revert to previous value
                with get_connection(DB_PATH) as conn:
                    prev_mode = get_setting(conn, "export_save_mode") or "template_folder"
                label_map = {
                    "template_folder": "Folder template (default)",
                    "hr_reports": "Documents/HR Reports/",
                    "custom": "Pilih folder lain...",
                }
                self.save_dest_var.set(label_map[prev_mode])
                return
            with get_connection(DB_PATH) as conn:
                set_setting(conn, "export_save_custom_path", chosen)
                set_setting(conn, "export_save_mode", "custom")
        else:
            with get_connection(DB_PATH) as conn:
                set_setting(conn, "export_save_mode", mode)

    def _resolve_save_destination(self, template_path: Path) -> Path:
        """Returns the directory to save export based on current save mode.

        Falls back to template's parent folder on PermissionError or other
        OSError (e.g., locked-down enterprise workstation, redirected roaming
        profile). User sees a warning toast but export proceeds.
        """
        with get_connection(DB_PATH) as conn:
            mode = get_setting(conn, "export_save_mode") or "template_folder"
            custom = get_setting(conn, "export_save_custom_path") or ""
        if mode == "hr_reports":
            target = Path.home() / "Documents" / "HR Reports"
            try:
                target.mkdir(parents=True, exist_ok=True)
                return target
            except OSError as e:
                feedback.show_warning(
                    self, "Folder HR Reports tidak bisa dibuat",
                    f"Fallback ke folder template.\n\n{e}",
                )
                return template_path.parent
        if mode == "custom" and custom:
            custom_path = Path(custom)
            if custom_path.exists():
                return custom_path
            # Custom path is stale — folder was deleted/moved. Fall back.
            feedback.show_warning(
                self, "Folder custom tidak ditemukan",
                f"Fallback ke folder template.\n\nFolder hilang: {custom}",
            )
            return template_path.parent
        # default: template's parent
        return template_path.parent

    # ── Busy guard (one scope shared by export + generate actions) ──

    def _screen_action_buttons(self) -> list:
        """Every button that must freeze while an export/generate runs:
        the file-chip actions + both Generate CTAs (those that exist)."""
        buttons = list(self.chip.action_buttons)
        for name in ("_gen_bulanan_btn", "_gen_mingguan_btn"):
            btn = getattr(self, name, None)
            if btn is not None:
                buttons.append(btn)
        return buttons

    def _acquire_busy(self, primary) -> BusyGuard | None:
        """Acquire the screen-wide busy scope. Returns the guard, or None
        when an operation is already running (double-click → caller no-ops).

        The clicked primary is passed first so BusyGuard shows "Memproses…"
        on it; every other action button just gets disabled. The guard is
        rebuilt per acquire because the chip's buttons are recreated on
        every set_content()."""
        if self._busy_guard is not None and self._busy_guard.busy:
            return None
        ordered = [primary] + [
            b for b in self._screen_action_buttons() if b is not primary
        ]
        guard = BusyGuard(*ordered, busy_text="Memproses…")
        guard.acquire()
        self._busy_guard = guard
        return guard

    # ── Export-mode actions ──

    def _preview_file(self):
        """R7 — generate the filled .xlsx in a fresh temp subdir (in the
        background) and open with the default viewer.

        Uses timestamped subdir so repeated Preview clicks don't collide on
        Windows file locks (Excel holds exclusive write lock when file is open).
        """
        if not self._selected:
            return
        guard = self._acquire_busy(self._chip_preview_btn)
        if guard is None:
            return
        # Gather inputs on the UI thread before spawning the worker
        db_path, template = DB_PATH, self._selected
        tmp_dir = Path(tempfile.gettempdir()) / f"hr-preview-{int(time.time())}"
        run_bg(
            self,
            work=lambda progress: preview_fill_work(db_path, template, tmp_dir),
            on_done=lambda out_path: self._on_preview_done(guard, out_path),
            on_error=lambda exc: self._on_preview_error(guard, exc),
        )

    def _on_preview_done(self, guard: BusyGuard, out_path: Path):
        guard.release()  # release before the (blocking) failure dialog below
        try:
            os.startfile(str(out_path))
        except Exception as e:
            feedback.show_warning(
                self, "Tidak bisa buka file",
                f"File tergenerate di:\n{out_path}\n\nTapi gagal dibuka otomatis:\n{e}",
            )

    def _on_preview_error(self, guard: BusyGuard, exc: Exception):
        guard.release()
        feedback.show_error(self, "Error generate preview", str(exc))

    def _pick(self):
        if self._busy_guard is not None and self._busy_guard.busy:
            return  # an export/generate is running — don't rebuild the chip mid-flight

        # Reset state from any previous selection
        self._filename_mismatch = False
        self._detected_ym = None

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

        # R2 — smart filename detection: warn if file mentions different month
        detected_ym = detect_year_month_from_filename(self._selected)
        with get_connection(DB_PATH) as conn:
            current_ym = get_setting(conn, "current_month") or ""
        self._filename_mismatch = bool(detected_ym and current_ym and detected_ym != current_ym)
        self._detected_ym = detected_ym

        with get_connection(DB_PATH) as conn:
            set_setting(conn, "last_export_template_folder", str(self._selected.parent))

        # Run dry-run preview
        try:
            with get_connection(DB_PATH) as conn:
                out_path, summary = fill_monthly_report(
                    self._selected, conn, dry_run=True,
                )
        except Exception as e:
            feedback.show_error(self, "Error preview", str(e))
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
        guard = self._acquire_busy(self._chip_export_btn)
        if guard is None:
            return
        # Gather inputs on the UI thread before spawning the worker
        db_path, template = DB_PATH, self._selected
        out_dir = self._resolve_save_destination(template)
        run_bg(
            self,
            work=lambda progress: export_fill_work(db_path, template, out_dir),
            on_done=lambda result: self._on_export_done(guard, result),
            on_error=lambda exc: self._on_export_error(guard, exc),
        )

    def _on_export_done(self, guard: BusyGuard, result):
        out_path, summary = result
        try:
            self._render_result_strip(out_path, summary)
            self._refresh_history()
            # Reset mismatch flag — action already done, banner shouldn't say "akan dimasukkan"
            self._filename_mismatch = False
            self._detected_ym = None
            self._update_banner()
        finally:
            guard.release()

    def _on_export_error(self, guard: BusyGuard, exc: Exception):
        guard.release()
        feedback.show_error(self, "Error export", str(exc))

    def _build_generate_mode(self, parent):
        """Generate mode — build a report from the database. Sub-modes:
        Bulanan (whole month) and Mingguan (one week)."""
        ctk.CTkLabel(
            parent,
            text="Buat file laporan dari database - tidak perlu template",
            font=FONT_SMALL, text_color=COLOR_TEXT_DIM,
        ).pack(anchor="w", pady=(0, SPACE_MD))

        sub = ctk.CTkFrame(parent, fg_color="transparent")
        sub.pack(anchor="w", pady=(0, SPACE_MD))
        self._gen_sub = "bulanan"
        self._gen_sub_btns = {}
        for sub_mode, label in (("bulanan", "Bulanan"), ("mingguan", "Mingguan")):
            b = ctk.CTkButton(
                sub, text=label, width=120, height=30,
                command=lambda s=sub_mode: self._show_gen_sub(s),
                font=FONT_BODY_BOLD,
            )
            b.pack(side="left", padx=(0, SPACE_XS))
            self._gen_sub_btns[sub_mode] = b

        self._gen_bulanan_panel = ctk.CTkFrame(parent, fg_color="transparent")
        self._gen_mingguan_panel = ctk.CTkFrame(parent, fg_color="transparent")
        self._build_gen_bulanan(self._gen_bulanan_panel)
        self._build_gen_mingguan(self._gen_mingguan_panel)
        self._show_gen_sub("bulanan")

    def _show_gen_sub(self, sub_mode):
        self._gen_sub = sub_mode
        for s, btn in self._gen_sub_btns.items():
            if s == sub_mode:
                btn.configure(
                    fg_color=COLOR_ACCENT, text_color=COLOR_BG,
                    hover_color=COLOR_ACCENT_HOVER,
                )
            else:
                btn.configure(
                    fg_color=COLOR_SURFACE, text_color=COLOR_TEXT_DIM,
                    hover_color=COLOR_SURFACE_HIGH,
                )
        self._gen_bulanan_panel.pack_forget()
        self._gen_mingguan_panel.pack_forget()
        panel = (
            self._gen_bulanan_panel if sub_mode == "bulanan"
            else self._gen_mingguan_panel
        )
        panel.pack(fill="both", expand=True)

    def _build_gen_bulanan(self, parent):
        ctk.CTkLabel(
            parent, text="PILIH BULAN", font=FONT_LABEL,
            text_color=COLOR_TEXT_MUTED,
        ).pack(anchor="w", padx=SPACE_XS)

        with get_connection(DB_PATH) as conn:
            months = [r["year_month"] for r in list_months_with_stats(conn)]
            active = get_setting(conn, "current_month") or ""

        if not months:
            ctk.CTkLabel(
                parent, text="(belum ada data bulan - import fingerprint dulu)",
                font=FONT_BODY, text_color=COLOR_TEXT_MUTED,
            ).pack(anchor="w", padx=SPACE_XS, pady=SPACE_SM)
            return

        labels = [month_label(m) for m in months]
        self._gen_month_map = dict(zip(labels, months))
        default_label = month_label(active) if active in months else labels[0]
        self._gen_month_var = ctk.StringVar(value=default_label)
        ctk.CTkOptionMenu(
            parent, values=labels, variable=self._gen_month_var, width=280,
            font=FONT_BODY, fg_color=COLOR_SURFACE_HIGH,
            button_color=COLOR_BORDER, button_hover_color=COLOR_BORDER_STRONG,
            text_color=COLOR_TEXT,
        ).pack(anchor="w", padx=SPACE_XS, pady=(SPACE_XS, SPACE_MD))

        self._gen_bulanan_btn = ctk.CTkButton(
            parent, text="⚙ Generate Laporan Bulanan", height=36,
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
            text_color=COLOR_BG, font=FONT_BODY_BOLD,
            command=self._on_generate_bulanan,
        )
        self._gen_bulanan_btn.pack(anchor="w", padx=SPACE_XS)

    def _build_gen_mingguan(self, parent):
        with get_connection(DB_PATH) as conn:
            active = get_setting(conn, "current_month") or ""

        if not active:
            ctk.CTkLabel(
                parent, text="(belum ada bulan aktif - pilih di Active Month dulu)",
                font=FONT_BODY, text_color=COLOR_TEXT_MUTED,
            ).pack(anchor="w", padx=SPACE_XS, pady=SPACE_SM)
            return

        self._mingguan_weeks = list(weeks_in_month(active))
        if not self._mingguan_weeks:
            ctk.CTkLabel(
                parent, text="(tidak ada minggu di bulan aktif)",
                font=FONT_BODY, text_color=COLOR_TEXT_MUTED,
            ).pack(anchor="w", padx=SPACE_XS, pady=SPACE_SM)
            return

        ctk.CTkLabel(
            parent, text=f"PILIH MINGGU - {month_label(active)}",
            font=FONT_LABEL, text_color=COLOR_TEXT_MUTED,
        ).pack(anchor="w", padx=SPACE_XS)

        week_row = ctk.CTkFrame(parent, fg_color="transparent")
        week_row.pack(anchor="w", padx=SPACE_XS, pady=(SPACE_XS, SPACE_MD))
        self._mingguan_week_btns = {}
        for (n, start, end) in self._mingguan_weeks:
            b = ctk.CTkButton(
                week_row, text=f"Minggu {n}", width=95, height=30,
                command=lambda w=(n, start, end): self._on_select_week(w),
                font=FONT_BODY,
            )
            b.pack(side="left", padx=(0, SPACE_XS))
            self._mingguan_week_btns[n] = b
        self._on_select_week(self._mingguan_weeks[0])

        self._gen_mingguan_btn = ctk.CTkButton(
            parent, text="⚙ Generate Laporan Mingguan", height=36,
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
            text_color=COLOR_BG, font=FONT_BODY_BOLD,
            command=self._on_generate_mingguan,
        )
        self._gen_mingguan_btn.pack(anchor="w", padx=SPACE_XS)

    def _on_select_week(self, week):
        self._mingguan_sel = week
        n_sel = week[0]
        for n, btn in self._mingguan_week_btns.items():
            if n == n_sel:
                btn.configure(fg_color=COLOR_ACCENT, text_color=COLOR_BG)
            else:
                btn.configure(fg_color=COLOR_SURFACE, text_color=COLOR_TEXT_DIM)

    def _on_generate_mingguan(self):
        guard = self._acquire_busy(self._gen_mingguan_btn)
        if guard is None:
            return
        n, start, end = self._mingguan_sel
        default_name = f"Laporan Mingguan {start} sd {end}.xlsx"
        out_path = filedialog.asksaveasfilename(
            defaultextension=".xlsx", initialfile=default_name,
            filetypes=[("Excel files", "*.xlsx")],
            title=f"Simpan Laporan Mingguan (Minggu {n})",
        )
        if not out_path:
            guard.release()
            return
        db_path = DB_PATH
        run_bg(
            self,
            work=lambda progress: generate_mingguan_work(
                db_path, start, end, Path(out_path),
            ),
            on_done=lambda summary: self._on_generate_mingguan_done(
                guard, n, start, end, summary,
            ),
            on_error=lambda exc: self._on_generate_error(
                guard, "Error generate mingguan", exc,
            ),
        )

    def _on_generate_mingguan_done(self, guard: BusyGuard, n, start, end, summary):
        try:
            self._refresh_history()
            show_success_toast(
                self.winfo_toplevel(), title="Laporan Mingguan Dibuat",
                message=(
                    f"Minggu {n} ({start} sd {end}) disimpan.\n"
                    f"{summary.rows} baris · {summary.employees} pegawai"
                ),
            )
        finally:
            guard.release()

    def _on_generate_bulanan(self):
        guard = self._acquire_busy(self._gen_bulanan_btn)
        if guard is None:
            return
        year_month = self._gen_month_map[self._gen_month_var.get()]
        default_name = f"Laporan Bulanan {month_label(year_month)} [Auto Filled].xlsx"
        out_path = filedialog.asksaveasfilename(
            defaultextension=".xlsx", initialfile=default_name,
            filetypes=[("Excel files", "*.xlsx")],
            title=f"Simpan Laporan {month_label(year_month)}",
        )
        if not out_path:
            guard.release()
            return
        db_path = DB_PATH
        run_bg(
            self,
            work=lambda progress: generate_bulanan_work(
                db_path, year_month, Path(out_path),
            ),
            on_done=lambda summary: self._on_generate_bulanan_done(
                guard, year_month, summary,
            ),
            on_error=lambda exc: self._on_generate_error(
                guard, "Error generate laporan", exc,
            ),
        )

    def _on_generate_bulanan_done(self, guard: BusyGuard, year_month: str, summary):
        try:
            self._refresh_history()
            show_success_toast(
                self.winfo_toplevel(), title="Laporan Berhasil Dibuat",
                message=(
                    f"Laporan Bulanan {month_label(year_month)} disimpan.\n"
                    f"{summary.rows_generated} baris · {summary.na_count} NA"
                ),
            )
        finally:
            guard.release()

    def _on_generate_error(self, guard: BusyGuard, title: str, exc: Exception):
        guard.release()
        feedback.show_error(self, title, f"Tidak bisa generate file:\n{exc}")
