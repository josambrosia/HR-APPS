"""Modal editor for ONE attendance row — opened by clicking a Heatmap cell.

Edit an existing row, add one to an empty (nodata) cell, or delete. Derived
fields (issue / telat / kerja / lembur) recompute live from the punches; an
optional override pins the three numeric fields when the machine's numbers
differ (e.g. break deduction). Save stamps manual_edited_at; delete snapshots
the DB first. Follows the BatchResolveDialog modal pattern. See spec §6.
"""
from typing import Callable, Optional

import customtkinter as ctk

from src.config import DB_PATH
from src.db.connection import get_connection
from src.db.settings import get_setting
from src.db.attendance import (
    get_attendance, save_manual_attendance, delete_attendance)
from src.db import backup as backup_mod
from src.core.attendance_calc import recompute, to_minutes
from src.core.week_utils import hari_name, MONTH_NAMES_ID
from src.core.session_state import notify_data_changed
from src.ui import feedback
from src.ui.theme import (
    COLOR_BG, COLOR_SURFACE, COLOR_SURFACE_HIGH, COLOR_BORDER,
    COLOR_ACCENT, COLOR_ACCENT_HOVER, COLOR_ACCENT_TINT_BORDER,
    COLOR_INFO, COLOR_SUCCESS, COLOR_WARN, COLOR_ERROR,
    COLOR_TEXT, COLOR_TEXT_DIM, COLOR_TEXT_MUTED,
    FONT_HEADING, FONT_BODY, FONT_BODY_BOLD, FONT_SMALL, FONT_LABEL,
    FONT_MONO_DATA,
    SPACE_XS, SPACE_SM, SPACE_MD, SPACE_LG,
    RADIUS_MD,
)

_TIPE_OPTIONS = ["Hari Kerja", "Hari Libur", "Istirahat"]
DIALOG_W = 440


def _fmt_tanggal(iso: str) -> str:
    try:
        y, m, d = iso.split("-")
        return f"{hari_name(iso)}, {int(d)} {MONTH_NAMES_ID[int(m)]} {y}"
    except (ValueError, KeyError):
        return iso


def _parse_int(s, fallback):
    try:
        return int(str(s).strip())
    except (TypeError, ValueError):
        return fallback


def _parse_float(s, fallback):
    try:
        return round(float(str(s).strip().replace(",", ".")), 1)
    except (TypeError, ValueError):
        return fallback


class AttendanceEditDialog(ctk.CTkToplevel):
    def __init__(self, parent, *, employee_id: int, nama: str, tanggal: str,
                 on_saved: Callable[[], None], on_deleted: Callable[[], None]):
        super().__init__(parent)
        self._eid = employee_id
        self._nama = nama
        self._tanggal = tanggal
        self._on_saved = on_saved
        self._on_deleted = on_deleted
        self._override_open = False
        self._last_calc = {"has_issue": 0, "terlambat_menit": 0,
                           "kerja_jam": 0.0, "lembur_jam": 0.0}

        with get_connection(DB_PATH) as conn:
            self._sched_start = get_setting(conn, "schedule_start", default="08.00")
            self._sched_end = get_setting(conn, "schedule_end", default="16.00")
            self._existing = get_attendance(conn, employee_id=employee_id, tanggal=tanggal)

        self.title("Edit Absensi" if self._existing else "Tambah Absensi")
        self.configure(fg_color=COLOR_BG)
        self.resizable(False, False)
        self.transient(parent)

        self._build()

        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        h = self.winfo_reqheight()
        x, y = (sw - DIALOG_W) // 2, max(0, (sh - h) // 2)
        self.geometry(f"{DIALOG_W}x{h}+{x}+{y}")

        self.after(50, lambda: (self.grab_set(), self.focus_set()))
        self.bind("<Escape>", lambda _e: self._close())
        self.bind("<Return>", lambda _e: (self._save(), "break")[1])
        self.protocol("WM_DELETE_WINDOW", self._close)

    # ---------- build ----------
    def _label(self, text):
        ctk.CTkLabel(self, text=text, font=FONT_LABEL, text_color=COLOR_TEXT_MUTED,
                     anchor="w").pack(fill="x", padx=SPACE_LG, pady=(SPACE_SM, 2))

    def _entry(self, parent, value=""):
        e = ctk.CTkEntry(parent, fg_color=COLOR_SURFACE_HIGH, border_width=1,
                         border_color=COLOR_BORDER, text_color=COLOR_TEXT, font=FONT_BODY)
        if value:
            e.insert(0, value)
        return e

    def _build(self):
        ex = self._existing or {}
        ctk.CTkLabel(self, text=self._nama, font=FONT_HEADING, text_color=COLOR_TEXT,
                     anchor="w").pack(fill="x", padx=SPACE_LG, pady=(SPACE_LG, 0))
        ctk.CTkLabel(self, text=_fmt_tanggal(self._tanggal), font=FONT_SMALL,
                     text_color=COLOR_TEXT_DIM, anchor="w").pack(
            fill="x", padx=SPACE_LG, pady=(2, SPACE_SM))

        # Tipe
        self._label("Tipe Hari")
        self._tipe_var = ctk.StringVar(value=ex.get("tipe") or "Hari Kerja")
        ctk.CTkOptionMenu(
            self, values=_TIPE_OPTIONS, variable=self._tipe_var,
            command=self._recompute_preview, fg_color=COLOR_SURFACE_HIGH,
            button_color=COLOR_ACCENT, button_hover_color=COLOR_ACCENT_HOVER,
            text_color=COLOR_TEXT, font=FONT_BODY,
        ).pack(fill="x", padx=SPACE_LG)

        # Masuk + Keluar
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=SPACE_LG, pady=(SPACE_SM, 0))
        row.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkLabel(row, text="MASUK", font=FONT_LABEL, text_color=COLOR_TEXT_MUTED,
                     anchor="w").grid(row=0, column=0, sticky="w", padx=(0, SPACE_SM))
        ctk.CTkLabel(row, text="KELUAR", font=FONT_LABEL, text_color=COLOR_TEXT_MUTED,
                     anchor="w").grid(row=0, column=1, sticky="w")
        self._masuk = self._entry(row, ex.get("masuk") or "")
        self._keluar = self._entry(row, ex.get("keluar") or "")
        self._masuk.grid(row=1, column=0, sticky="ew", padx=(0, SPACE_SM))
        self._keluar.grid(row=1, column=1, sticky="ew")
        for e in (self._masuk, self._keluar):
            e.bind("<KeyRelease>", self._recompute_preview)

        # Jadwal
        self._label("Jadwal")
        self._jadwal = self._entry(self, ex.get("jadwal") or "")
        self._jadwal.pack(fill="x", padx=SPACE_LG)
        ctk.CTkLabel(self, text="teks bebas · tidak dipakai perhitungan",
                     font=FONT_SMALL, text_color=COLOR_TEXT_MUTED, anchor="w").pack(
            fill="x", padx=SPACE_LG, pady=(2, SPACE_MD))

        # Auto box
        self._auto_box = ctk.CTkFrame(self, fg_color=COLOR_SURFACE, border_width=1,
                                      border_color=COLOR_ACCENT_TINT_BORDER,
                                      corner_radius=RADIUS_MD)
        self._auto_box.pack(fill="x", padx=SPACE_LG)
        ctk.CTkLabel(self._auto_box, text="◆ DIHITUNG OTOMATIS", font=FONT_LABEL,
                     text_color=COLOR_ACCENT_HOVER, anchor="w").pack(
            fill="x", padx=SPACE_MD, pady=(SPACE_SM, SPACE_XS))
        grid = ctk.CTkFrame(self._auto_box, fg_color="transparent")
        grid.pack(fill="x", padx=SPACE_MD, pady=(0, SPACE_SM))
        grid.grid_columnconfigure((0, 1), weight=1)
        self._status_lbl = self._metric(grid, 0, 0, "Status", "—")
        self._telat_lbl = self._metric(grid, 0, 1, "Telat", "—")
        self._kerja_lbl = self._metric(grid, 1, 0, "Kerja", "—")
        self._lembur_lbl = self._metric(grid, 1, 1, "Lembur", "—")

        # Override (collapsible)
        self._ov_toggle = ctk.CTkLabel(
            self, text="▸ Angka manual (override)", font=FONT_SMALL,
            text_color=COLOR_TEXT_MUTED, anchor="w", cursor="hand2")
        self._ov_toggle.pack(fill="x", padx=SPACE_LG, pady=(SPACE_XS, 0))
        self._ov_toggle.bind("<Button-1>", lambda _e: self._toggle_override())
        self._ov_frame = ctk.CTkFrame(self, fg_color="transparent")
        ovr = self._ov_frame
        ovr.grid_columnconfigure((0, 1, 2), weight=1)
        for i, cap in enumerate(("Telat (mnt)", "Kerja (jam)", "Lembur (jam)")):
            ctk.CTkLabel(ovr, text=cap, font=FONT_SMALL, text_color=COLOR_TEXT_MUTED,
                         anchor="w").grid(row=0, column=i, sticky="w", padx=(0, SPACE_XS))
        self._ov_telat = self._entry(ovr)
        self._ov_kerja = self._entry(ovr)
        self._ov_lembur = self._entry(ovr)
        self._ov_telat.grid(row=1, column=0, sticky="ew", padx=(0, SPACE_XS))
        self._ov_kerja.grid(row=1, column=1, sticky="ew", padx=(0, SPACE_XS))
        self._ov_lembur.grid(row=1, column=2, sticky="ew")

        # Footer
        self._footer = ctk.CTkFrame(self, fg_color="transparent")
        self._footer.pack(fill="x", padx=SPACE_LG, pady=(SPACE_MD, SPACE_LG))
        if self._existing:
            ctk.CTkButton(
                self._footer, text="🗑 Hapus", command=self._delete, width=90,
                fg_color="transparent", border_width=1, border_color=COLOR_ERROR,
                text_color=COLOR_ERROR, hover_color=COLOR_SURFACE_HIGH,
                font=FONT_BODY_BOLD, corner_radius=RADIUS_MD,
            ).pack(side="left")
        ctk.CTkButton(
            self._footer, text="Simpan", command=self._save, width=110,
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER, text_color=COLOR_BG,
            font=FONT_BODY_BOLD, corner_radius=RADIUS_MD,
        ).pack(side="right")
        ctk.CTkButton(
            self._footer, text="Batal", command=self._close, width=90,
            fg_color="transparent", border_width=1, border_color=COLOR_INFO,
            text_color=COLOR_INFO, hover_color=COLOR_SURFACE_HIGH,
            font=FONT_BODY_BOLD, corner_radius=RADIUS_MD,
        ).pack(side="right", padx=(0, SPACE_SM))

        self._recompute_preview()

    def _metric(self, parent, r, c, cap, val):
        cell = ctk.CTkFrame(parent, fg_color="transparent")
        cell.grid(row=r, column=c, sticky="w", pady=2)
        ctk.CTkLabel(cell, text=cap, font=FONT_SMALL, text_color=COLOR_TEXT_DIM).pack(side="left")
        lbl = ctk.CTkLabel(cell, text=val, font=FONT_MONO_DATA, text_color=COLOR_TEXT)
        lbl.pack(side="left", padx=(SPACE_XS, 0))
        return lbl

    # ---------- behavior ----------
    def _recompute_preview(self, *_):
        d = recompute(
            tipe=self._tipe_var.get(),
            masuk=self._masuk.get().strip() or None,
            keluar=self._keluar.get().strip() or None,
            schedule_start=self._sched_start, schedule_end=self._sched_end)
        self._last_calc = d
        if d["has_issue"]:
            self._status_lbl.configure(text="⚠ Bermasalah", text_color=COLOR_WARN)
        else:
            self._status_lbl.configure(text="✓ Beres", text_color=COLOR_SUCCESS)
        self._telat_lbl.configure(text=f"{d['terlambat_menit']} mnt")
        self._kerja_lbl.configure(text=f"{d['kerja_jam']} jam")
        self._lembur_lbl.configure(text=f"{d['lembur_jam']} jam")
        return d

    def _toggle_override(self):
        self._override_open = not self._override_open
        if self._override_open:
            c = self._last_calc
            for entry, val in ((self._ov_telat, c["terlambat_menit"]),
                               (self._ov_kerja, c["kerja_jam"]),
                               (self._ov_lembur, c["lembur_jam"])):
                entry.delete(0, "end"); entry.insert(0, str(val))
            self._ov_frame.pack(fill="x", padx=SPACE_LG, pady=(SPACE_XS, 0),
                                before=self._footer)
            self._ov_toggle.configure(text="▾ Angka manual (override)")
        else:
            self._ov_frame.pack_forget()
            self._ov_toggle.configure(text="▸ Angka manual (override)")
        try:
            self.update_idletasks()
            self.geometry(f"{DIALOG_W}x{self.winfo_reqheight()}")
        except Exception:
            pass

    def _regrab(self):
        try:
            self.grab_set()
        except Exception:
            pass

    def _save(self):
        masuk = self._masuk.get().strip() or None
        keluar = self._keluar.get().strip() or None
        for label, val in (("Masuk", masuk), ("Keluar", keluar)):
            if val is not None and to_minutes(val) is None:
                feedback.show_warning(
                    self, f"{label} tidak valid",
                    f"Format jam harus HH:MM (mis. 08:00). '{val}' tidak dikenali.")
                self._regrab()
                return
        calc = self._recompute_preview()
        terlambat, kerja, lembur = (calc["terlambat_menit"],
                                    calc["kerja_jam"], calc["lembur_jam"])
        if self._override_open:
            terlambat = _parse_int(self._ov_telat.get(), terlambat)
            kerja = _parse_float(self._ov_kerja.get(), kerja)
            lembur = _parse_float(self._ov_lembur.get(), lembur)
        with get_connection(DB_PATH) as conn:
            save_manual_attendance(
                conn, employee_id=self._eid, tanggal=self._tanggal,
                hari=hari_name(self._tanggal), tipe=self._tipe_var.get(),
                jadwal=self._jadwal.get().strip() or None,
                masuk=masuk, keluar=keluar, kerja_jam=kerja, lembur_jam=lembur,
                terlambat_menit=terlambat, has_issue=calc["has_issue"])
        notify_data_changed()
        self._close()
        self._on_saved()

    def _delete(self):
        if not feedback.ask_yes_no(
            self, "Hapus baris?",
            f"Hapus data absensi {self._nama} tanggal {self._tanggal}?\n"
            "Database di-backup dulu sebelum dihapus."):
            self._regrab()
            return
        try:
            backup_mod.create_backup(DB_PATH, reason="hapus")
        except Exception as exc:  # noqa: BLE001 — never delete without a backup
            feedback.show_error(self, "Backup gagal, hapus dibatalkan", str(exc))
            self._regrab()
            return
        with get_connection(DB_PATH) as conn:
            delete_attendance(conn, employee_id=self._eid, tanggal=self._tanggal)
        notify_data_changed()
        self._close()
        self._on_deleted()

    def _close(self):
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()
