"""Dialog detail + verifikasi satu baris lembur (v26).

Menampilkan identitas, jam, durasi terdeteksi, linimasa status, kolom jam
disetujui (aktif saat Diterima), catatan, dan tombol aksi sesuai status.
Koreksi status apa pun selalu lewat konfirmasi.
"""
from datetime import datetime

import customtkinter as ctk

from src.config import DB_PATH
from src.core.overtime import OvertimeRow, format_duration
from src.core.session_state import notify_data_changed
from src.core.week_utils import MONTH_NAMES_ID, hari_name
from src.db.connection import get_connection
from src.db.overtime import apply_status, set_note_approved
from src.ui import feedback
from src.ui.theme import (
    COLOR_BG, COLOR_SURFACE, COLOR_SURFACE_HIGH, COLOR_BORDER,
    COLOR_ACCENT, COLOR_ACCENT_HOVER, COLOR_INFO, COLOR_SUCCESS, COLOR_WARN,
    COLOR_ERROR, COLOR_TEXT, COLOR_TEXT_DIM, COLOR_TEXT_MUTED,
    FONT_HEADING, FONT_BODY, FONT_BODY_BOLD, FONT_SMALL, FONT_LABEL,
    FONT_MONO_DATA, SPACE_XS, SPACE_SM, SPACE_MD, SPACE_LG, RADIUS_MD,
)

DIALOG_W = 460

STATUS_LABELS = {
    "open": "Open",
    "diajukan": "Diajukan",
    "diterima": "Diterima",
    "tidak_diterima": "Tidak Diterima",
}
STATUS_COLORS = {
    "open": COLOR_WARN,
    "diajukan": COLOR_INFO,
    "diterima": COLOR_SUCCESS,
    "tidak_diterima": COLOR_ERROR,
}


def _fmt_tanggal(iso: str) -> str:
    try:
        y, m, d = iso.split("-")
        return f"{hari_name(iso)}, {int(d)} {MONTH_NAMES_ID[int(m)]} {y}"
    except (ValueError, KeyError):
        return iso


def _fmt_ts(iso: str | None) -> str:
    if not iso:
        return "—"
    try:
        return datetime.fromisoformat(iso).strftime("%d %b %Y %H:%M")
    except ValueError:
        return iso


class OvertimeDetailDialog(ctk.CTkToplevel):
    def __init__(self, parent, row: OvertimeRow, on_saved):
        super().__init__(parent)
        self._row = row
        self._on_saved = on_saved
        self.title("Detail Lembur")
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
        self.protocol("WM_DELETE_WINDOW", self._close)

    # ---------- build ----------
    def _metric(self, parent, r, c, cap, val, color=COLOR_TEXT):
        cell = ctk.CTkFrame(parent, fg_color="transparent")
        cell.grid(row=r, column=c, sticky="w", pady=2)
        ctk.CTkLabel(cell, text=cap, font=FONT_SMALL,
                     text_color=COLOR_TEXT_DIM).pack(side="left")
        ctk.CTkLabel(cell, text=val, font=FONT_MONO_DATA,
                     text_color=color).pack(side="left", padx=(SPACE_XS, 0))

    def _build(self):
        r = self._row
        ctk.CTkLabel(self, text=r.nama, font=FONT_HEADING,
                     text_color=COLOR_TEXT, anchor="w").pack(
            fill="x", padx=SPACE_LG, pady=(SPACE_LG, 0))
        ctk.CTkLabel(self, text=_fmt_tanggal(r.tanggal), font=FONT_SMALL,
                     text_color=COLOR_TEXT_DIM, anchor="w").pack(
            fill="x", padx=SPACE_LG, pady=(2, SPACE_SM))

        box = ctk.CTkFrame(self, fg_color=COLOR_SURFACE, border_width=1,
                           border_color=COLOR_BORDER, corner_radius=RADIUS_MD)
        box.pack(fill="x", padx=SPACE_LG)
        grid = ctk.CTkFrame(box, fg_color="transparent")
        grid.pack(fill="x", padx=SPACE_MD, pady=SPACE_SM)
        grid.grid_columnconfigure((0, 1), weight=1)
        self._metric(grid, 0, 0, "Masuk", r.masuk or "—")
        self._metric(grid, 0, 1, "Keluar", r.keluar or "—")
        self._metric(grid, 1, 0, "Lembur", format_duration(r.minutes),
                     COLOR_ACCENT if r.minutes else COLOR_TEXT_DIM)
        self._metric(grid, 1, 1, "Jenis", "Libur/akhir pekan"
                     if r.is_holiday else "Hari kerja")
        if not r.qualifies:
            ctk.CTkLabel(box, text="⚠ Tidak lagi memenuhi syarat deteksi",
                         font=FONT_SMALL, text_color=COLOR_WARN,
                         anchor="w").pack(fill="x", padx=SPACE_MD,
                                          pady=(0, SPACE_SM))
        if r.changed:
            ctk.CTkLabel(box, text="⚠ Data absensi berubah setelah keputusan "
                                   "terakhir",
                         font=FONT_SMALL, text_color=COLOR_WARN,
                         anchor="w").pack(fill="x", padx=SPACE_MD,
                                          pady=(0, SPACE_SM))

        # Status + linimasa
        st = ctk.CTkFrame(self, fg_color="transparent")
        st.pack(fill="x", padx=SPACE_LG, pady=(SPACE_MD, 0))
        ctk.CTkLabel(st, text="Status:", font=FONT_SMALL,
                     text_color=COLOR_TEXT_DIM).pack(side="left")
        ctk.CTkLabel(st, text=STATUS_LABELS.get(r.status, r.status),
                     font=FONT_BODY_BOLD,
                     text_color=STATUS_COLORS.get(r.status, COLOR_TEXT)).pack(
            side="left", padx=(SPACE_XS, SPACE_MD))
        ctk.CTkLabel(
            st,
            text=f"Diajukan: {_fmt_ts(r.submitted_at)} · "
                 f"Diputus: {_fmt_ts(r.decided_at)}",
            font=FONT_SMALL, text_color=COLOR_TEXT_MUTED).pack(side="left")

        # Jam disetujui
        self._label("JAM DISETUJUI (kosongkan = seluruh jam terdeteksi)")
        ap = ctk.CTkFrame(self, fg_color="transparent")
        ap.pack(fill="x", padx=SPACE_LG)
        base_min = r.approved_minutes if r.approved_minutes is not None else r.minutes
        self._ap_jam = self._entry(ap, str(base_min // 60), width=54)
        ctk.CTkLabel(ap, text="j", font=FONT_SMALL,
                     text_color=COLOR_TEXT_DIM).pack(side="left", padx=(2, SPACE_SM))
        self._ap_menit = self._entry(ap, str(base_min % 60), width=54)
        ctk.CTkLabel(ap, text="m", font=FONT_SMALL,
                     text_color=COLOR_TEXT_DIM).pack(side="left", padx=(2, 0))

        # Catatan
        self._label("CATATAN")
        self._note = ctk.CTkTextbox(self, height=56, fg_color=COLOR_SURFACE_HIGH,
                                    border_width=1, border_color=COLOR_BORDER,
                                    text_color=COLOR_TEXT, font=FONT_BODY)
        self._note.pack(fill="x", padx=SPACE_LG)
        if r.note:
            self._note.insert("1.0", r.note)

        # Aksi
        self._footer = ctk.CTkFrame(self, fg_color="transparent")
        self._footer.pack(fill="x", padx=SPACE_LG, pady=(SPACE_MD, SPACE_LG))
        self._build_actions()
        ctk.CTkButton(
            self._footer, text="Tutup", command=self._close, width=80,
            fg_color="transparent", border_width=1, border_color=COLOR_INFO,
            text_color=COLOR_INFO, hover_color=COLOR_SURFACE_HIGH,
            font=FONT_BODY_BOLD, corner_radius=RADIUS_MD,
        ).pack(side="right", padx=(SPACE_SM, 0))

    def _label(self, text):
        ctk.CTkLabel(self, text=text, font=FONT_LABEL,
                     text_color=COLOR_TEXT_MUTED, anchor="w").pack(
            fill="x", padx=SPACE_LG, pady=(SPACE_MD, 2))

    def _entry(self, parent, value="", width=80):
        e = ctk.CTkEntry(parent, width=width, fg_color=COLOR_SURFACE_HIGH,
                         border_width=1, border_color=COLOR_BORDER,
                         text_color=COLOR_TEXT, font=FONT_BODY)
        e.insert(0, value)
        e.pack(side="left")
        return e

    def _action_btn(self, text, command, color=COLOR_ACCENT):
        ctk.CTkButton(
            self._footer, text=text, command=command, width=120,
            fg_color=color, hover_color=COLOR_ACCENT_HOVER,
            text_color=COLOR_BG, font=FONT_BODY_BOLD, corner_radius=RADIUS_MD,
        ).pack(side="left", padx=(0, SPACE_SM))

    def _ghost_btn(self, text, command, color=COLOR_INFO):
        ctk.CTkButton(
            self._footer, text=text, command=command, width=130,
            fg_color="transparent", border_width=1, border_color=color,
            text_color=color, hover_color=COLOR_SURFACE_HIGH,
            font=FONT_BODY_BOLD, corner_radius=RADIUS_MD,
        ).pack(side="left", padx=(0, SPACE_SM))

    def _build_actions(self):
        s = self._row.status
        if s == "open":
            self._action_btn("Ajukan ke Pemilik", lambda: self._apply("diajukan"))
        elif s == "diajukan":
            self._action_btn("Diterima", lambda: self._apply("diterima"),
                             COLOR_SUCCESS)
            self._action_btn("Tidak Diterima",
                             lambda: self._apply("tidak_diterima"), COLOR_ERROR)
            self._ghost_btn("Kembalikan ke Open",
                            lambda: self._apply("open"), COLOR_TEXT_MUTED)
        else:
            other = "tidak_diterima" if s == "diterima" else "diterima"
            other_label = ("Tidak Diterima" if other == "tidak_diterima"
                           else "Diterima")
            other_color = COLOR_ERROR if other == "tidak_diterima" else COLOR_SUCCESS
            self._action_btn(other_label, lambda: self._apply(other), other_color)
            self._ghost_btn("Kembalikan ke Diajukan",
                            lambda: self._apply("diajukan"), COLOR_TEXT_MUTED)
        if s != "open":
            self._ghost_btn("Simpan Catatan", self._save_note)

    # ---------- behavior ----------
    def _parse_approved(self):
        """(minutes | None, error) — None berarti pakai jam terdeteksi."""
        try:
            j = int(self._ap_jam.get().strip() or 0)
            m = int(self._ap_menit.get().strip() or 0)
        except ValueError:
            return None, "Jam disetujui harus angka."
        if j < 0 or m < 0 or m > 59:
            return None, "Menit harus 0–59 dan tidak negatif."
        total = j * 60 + m
        if total > self._row.minutes:
            return None, (f"Jam disetujui ({format_duration(total)}) tidak boleh "
                          f"melebihi jam terdeteksi "
                          f"({format_duration(self._row.minutes)}).")
        return total, None

    def _note_text(self):
        return self._note.get("1.0", "end").strip() or None

    def _apply(self, status: str):
        label = STATUS_LABELS.get(status, status)
        if status != "diajukan":
            if not feedback.ask_yes_no(
                self, "Ubah status?",
                f"Ubah status baris {self._row.nama} "
                f"({self._row.tanggal}) menjadi \"{label}\"?",
            ):
                self._regrab()
                return
        approved = None
        if status == "diterima":
            approved, err = self._parse_approved()
            if err:
                feedback.show_warning(self, "Jam disetujui tidak valid", err)
                self._regrab()
                return
        note = self._note_text()
        with get_connection(DB_PATH) as conn:
            apply_status(
                conn, employee_id=self._row.employee_id,
                tanggal=self._row.tanggal, status=status,
                detected_minutes=self._row.minutes,
                approved_minutes=approved, note=note)
            if status != "open":
                set_note_approved(
                    conn, employee_id=self._row.employee_id,
                    tanggal=self._row.tanggal, note=note,
                    approved_minutes=approved)
        notify_data_changed()
        self._close()
        self._on_saved()

    def _save_note(self):
        approved = None
        if self._row.status == "diterima":
            approved, err = self._parse_approved()
            if err:
                feedback.show_warning(self, "Jam disetujui tidak valid", err)
                self._regrab()
                return
        with get_connection(DB_PATH) as conn:
            set_note_approved(
                conn, employee_id=self._row.employee_id,
                tanggal=self._row.tanggal, note=self._note_text(),
                approved_minutes=approved)
        notify_data_changed()
        self._close()
        self._on_saved()

    def _regrab(self):
        try:
            self.grab_set()
        except Exception:
            pass

    def _close(self):
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()
