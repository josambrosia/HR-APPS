import webbrowser
from datetime import datetime
from tkinter import messagebox

import customtkinter as ctk
import pyperclip

from src.config import DB_PATH
from src.db.connection import get_connection
from src.db.settings import get_setting
from src.db.wa_contacts import (
    contacted_map, is_contacted, mark_contacted, unmark_contacted,
)
from src.core.week_utils import full_month_range
from src.core.wa_message import build_wa_message, format_issue, wa_me_url
from src.ui.theme import (
    COLOR_BG, COLOR_SURFACE, COLOR_SURFACE_HIGH,
    COLOR_BORDER, COLOR_BORDER_STRONG,
    COLOR_ACCENT, COLOR_ACCENT_HOVER,
    COLOR_WARN, COLOR_ERROR, COLOR_SUCCESS,
    COLOR_TEXT, COLOR_TEXT_DIM, COLOR_TEXT_MUTED, COLOR_TEXT_DISABLED,
    FONT_HEADING, FONT_SUBHEAD, FONT_BODY, FONT_BODY_BOLD,
    FONT_SMALL, FONT_LABEL, FONT_MONO_SMALL,
    SPACE_XS, SPACE_SM, SPACE_MD, SPACE_LG,
    RADIUS_SM, RADIUS_MD, RADIUS_LG,
)

# WhatsApp-brand colors (screen-local, mirrors heatmap.py's local palette).
_WA_WALL       = "#0B141A"
_WA_BUBBLE     = "#005C4B"
_WA_BUBBLE_TX  = "#E9EDEA"
_WA_SEND       = "#00A884"
_WA_SEND_HOVER = "#06CF9C"
_WA_TICK       = "#53BDEB"
_WA_DAYPILL    = "#0C211B"
_WA_DAYPILL_TX = "#8AA69D"

_AVATAR_TINTS = ["#7C3AED", "#DB2777", "#0891B2", "#CA8A04", "#4F46E5", "#0D9488"]
_TONE_LABELS = {"Formal": "formal", "Ramah": "ramah"}


def _initials(nama: str) -> str:
    parts = [p for p in (nama or "").split() if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[1][0]).upper()


def _avatar_tint(nama: str) -> str:
    return _AVATAR_TINTS[sum(ord(c) for c in (nama or "")) % len(_AVATAR_TINTS)]


class WhatsAppAssistantScreen(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self.grid_columnconfigure(0, weight=0, minsize=288)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._current_employee_id = None
        self._current_month = ""
        self._tone = "formal"
        self._note = ""
        self._officer = ""
        self._emp = {}
        self._issues = []
        self._rows_cache = []
        self._contacted = {}
        self._preview = None
        self._note_box = None
        self._note_visible = False
        self._wall = None
        self._contact_btn = None
        self._search_var = ctk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._render_list())
        self._build()
        self._reload()

    # ---- layout -----------------------------------------------------------
    def _build(self):
        left = ctk.CTkFrame(self, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, SPACE_MD))
        left.grid_rowconfigure(2, weight=1)
        left.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(left, text="Pegawai · open issues", font=FONT_SUBHEAD,
                     text_color=COLOR_TEXT).grid(row=0, column=0, sticky="w",
                                                 pady=(0, SPACE_SM))
        search = ctk.CTkFrame(left, fg_color=COLOR_SURFACE, corner_radius=RADIUS_MD,
                              border_width=1, border_color=COLOR_BORDER)
        search.grid(row=1, column=0, sticky="ew", pady=(0, SPACE_SM))
        ctk.CTkLabel(search, text="⌕", font=FONT_BODY,
                     text_color=COLOR_TEXT_MUTED).pack(side="left", padx=(SPACE_SM, 0))
        ctk.CTkEntry(search, textvariable=self._search_var, placeholder_text="Cari nama…",
                     border_width=0, fg_color="transparent", height=30
                     ).pack(side="left", fill="x", expand=True, padx=(SPACE_XS, SPACE_SM))

        self.list_frame = ctk.CTkScrollableFrame(left, fg_color=COLOR_SURFACE,
                                                 corner_radius=RADIUS_MD)
        self.list_frame.grid(row=2, column=0, sticky="nsew")

        right = ctk.CTkFrame(self, fg_color=COLOR_SURFACE, border_width=1,
                             border_color=COLOR_BORDER, corner_radius=RADIUS_MD)
        right.grid(row=0, column=1, sticky="nsew")
        self.right = right
        self._show_empty("Pilih pegawai di kiri untuk menyusun pesan")

    def _show_empty(self, text):
        for w in self.right.winfo_children():
            w.destroy()
        self._preview = None
        ctk.CTkLabel(self.right, text=text, font=FONT_BODY,
                     text_color=COLOR_TEXT_MUTED).pack(pady=80)

    # ---- data + list ------------------------------------------------------
    def _reload(self):
        with get_connection(DB_PATH) as conn:
            month = get_setting(conn, "current_month") or ""
            self._current_month = month
            if not month:
                self._rows_cache, self._contacted = [], {}
                self._render_list(empty_msg="(belum ada bulan aktif — pilih di Active Month)")
                return
            start, end = full_month_range(month)
            rows = conn.execute(
                """
                SELECT e.id, e.nama, e.dept, e.phone, COUNT(*) AS open_cnt
                  FROM attendance_records ar
                  JOIN employees e ON ar.employee_id = e.id
                 WHERE ar.has_issue = 1 AND ar.reason_category IS NULL
                   AND ar.tanggal BETWEEN ? AND ?
                 GROUP BY e.id
                 ORDER BY e.nama
                """,
                (start, end),
            ).fetchall()
            self._rows_cache = [dict(r) for r in rows]
            self._contacted = contacted_map(conn, month)
        self._render_list()

    def _render_list(self, empty_msg="(tidak ada open issue)"):
        if not hasattr(self, "list_frame"):
            return
        for w in self.list_frame.winfo_children():
            w.destroy()
        q = self._search_var.get().strip().lower()
        rows = [r for r in self._rows_cache if q in r["nama"].lower()]
        if not rows:
            msg = "(tak ada nama yang cocok)" if q and self._rows_cache else empty_msg
            ctk.CTkLabel(self.list_frame, text=msg, font=FONT_BODY,
                         text_color=COLOR_TEXT_MUTED).pack(pady=20)
            return
        rows.sort(key=lambda r: (r["id"] in self._contacted, r["nama"].lower()))
        for r in rows:
            self._list_row(r)

    def _list_row(self, r):
        contacted = r["id"] in self._contacted
        has_phone = bool((r["phone"] or "").strip())
        row = ctk.CTkFrame(self.list_frame, fg_color="transparent")
        row.pack(fill="x", padx=SPACE_XS, pady=1)

        if contacted:
            dot, dot_c = "✓", COLOR_SUCCESS
        elif has_phone:
            dot, dot_c = "●", COLOR_SUCCESS
        else:
            dot, dot_c = "○", COLOR_TEXT_DISABLED
        ctk.CTkLabel(row, text=dot, font=FONT_MONO_SMALL, text_color=dot_c,
                     width=14).pack(side="left", padx=(SPACE_XS, 0))

        ctk.CTkButton(
            row, text=r["nama"], anchor="w", fg_color="transparent",
            hover_color=COLOR_SURFACE_HIGH, font=FONT_BODY,
            text_color=(COLOR_TEXT_DISABLED if contacted else COLOR_TEXT),
            command=lambda e=r["id"]: self._show_for(e),
        ).pack(side="left", fill="x", expand=True)

        badge = "✓" if contacted else str(r["open_cnt"])
        ctk.CTkLabel(row, text=badge,
                     fg_color=(COLOR_SURFACE_HIGH if contacted else COLOR_WARN),
                     text_color=(COLOR_SUCCESS if contacted else COLOR_BG),
                     font=FONT_MONO_SMALL, corner_radius=RADIUS_MD,
                     width=26, height=20).pack(side="right", padx=(SPACE_XS, SPACE_SM))

    # ---- compose ----------------------------------------------------------
    def _show_for(self, emp_id):
        self._current_employee_id = emp_id
        self._note = ""
        self._note_visible = False
        with get_connection(DB_PATH) as conn:
            emp = conn.execute(
                "SELECT nama, dept, phone FROM employees WHERE id = ?", (emp_id,)
            ).fetchone()
            start, end = full_month_range(self._current_month)
            issues = conn.execute(
                """
                SELECT tanggal, hari, masuk, keluar
                  FROM attendance_records
                 WHERE employee_id = ? AND has_issue = 1 AND reason_category IS NULL
                   AND tanggal BETWEEN ? AND ?
                 ORDER BY tanggal
                """,
                (emp_id, start, end),
            ).fetchall()
            self._officer = (get_setting(conn, "hr_officer_name") or "").strip()
            contacted = is_contacted(conn, employee_id=emp_id,
                                     year_month=self._current_month)
        if not emp or not issues:
            self._show_empty("(tidak ada open issue)")
            return
        self._emp = dict(emp)
        self._issues = [dict(i) for i in issues]
        self._build_compose(contacted)

    def _build_compose(self, contacted):
        for w in self.right.winfo_children():
            w.destroy()
        pad = SPACE_LG
        nama = self._emp["nama"]
        phone = (self._emp.get("phone") or "").strip()

        # identity header
        idbar = ctk.CTkFrame(self.right, fg_color="transparent")
        idbar.pack(fill="x", padx=pad, pady=(pad, SPACE_SM))
        ctk.CTkLabel(idbar, text=_initials(nama), font=FONT_HEADING,
                     text_color=COLOR_TEXT, fg_color=_avatar_tint(nama),
                     width=46, height=46, corner_radius=RADIUS_LG).pack(side="left")
        meta = ctk.CTkFrame(idbar, fg_color="transparent")
        meta.pack(side="left", fill="x", expand=True, padx=(SPACE_MD, 0))
        ctk.CTkLabel(meta, text=nama.title(), font=FONT_SUBHEAD,
                     text_color=COLOR_TEXT, anchor="w").pack(anchor="w")
        dept = self._emp.get("dept") or "—"
        sub = f"{dept}   ·   {phone}" if phone else dept
        ctk.CTkLabel(meta, text=sub, font=FONT_MONO_SMALL,
                     text_color=COLOR_TEXT_MUTED, anchor="w").pack(anchor="w", pady=(2, 0))
        if phone:
            pill_t, pill_c = "✓ Nomor tersedia", COLOR_SUCCESS
        else:
            pill_t, pill_c = "⚠ Nomor belum diset", COLOR_WARN
        ctk.CTkLabel(idbar, text=pill_t, font=FONT_LABEL,
                     text_color=pill_c).pack(side="right", anchor="n")

        # issue list
        issues_box = ctk.CTkFrame(self.right, fg_color="transparent")
        issues_box.pack(fill="x", padx=pad, pady=(0, SPACE_SM))
        ctk.CTkLabel(issues_box, text=f"{len(self._issues)} issue belum dikonfirmasi",
                     font=FONT_SMALL, text_color=COLOR_TEXT_DIM
                     ).pack(anchor="w", pady=(0, SPACE_XS))
        for it in self._issues:
            both_missing = it["masuk"] is None and it["keluar"] is None
            line = ctk.CTkFrame(issues_box, fg_color="transparent")
            line.pack(fill="x", pady=1)
            ctk.CTkLabel(line, text="■", width=12, font=FONT_MONO_SMALL,
                         text_color=(COLOR_ERROR if both_missing else COLOR_WARN)
                         ).pack(side="left")
            ctk.CTkLabel(line, text=format_issue(it["hari"], it["tanggal"], it["masuk"],
                                                 it["keluar"], self._current_month),
                         font=FONT_SMALL, text_color=COLOR_TEXT_DIM, anchor="w"
                         ).pack(side="left")

        # tone + note toggle
        tools = ctk.CTkFrame(self.right, fg_color="transparent")
        tools.pack(fill="x", padx=pad, pady=(SPACE_SM, SPACE_SM))
        seg = ctk.CTkSegmentedButton(
            tools, values=["Formal", "Ramah"], command=self._on_tone,
            font=FONT_SMALL, selected_color=COLOR_ACCENT,
            selected_hover_color=COLOR_ACCENT_HOVER, unselected_color=COLOR_SURFACE_HIGH,
            unselected_hover_color=COLOR_SURFACE_HIGH)
        seg.set("Formal" if self._tone == "formal" else "Ramah")
        seg.pack(side="left")
        self._note_btn = ctk.CTkButton(
            tools, text="＋ Catatan", width=96, fg_color="transparent",
            border_width=1, border_color=COLOR_BORDER_STRONG, text_color=COLOR_TEXT_DIM,
            hover_color=COLOR_SURFACE_HIGH, font=FONT_SMALL, command=self._toggle_note)
        self._note_btn.pack(side="left", padx=(SPACE_SM, 0))

        self._note_box = ctk.CTkTextbox(self.right, height=46, fg_color=COLOR_BG,
                                        border_width=1, border_color=COLOR_BORDER,
                                        text_color=COLOR_TEXT, font=FONT_BODY, wrap="word")
        self._note_box.bind("<KeyRelease>", lambda e: self._on_note())

        # WA preview (wallpaper + editable bubble)
        wall = ctk.CTkFrame(self.right, fg_color=_WA_WALL, corner_radius=RADIUS_MD)
        wall.pack(fill="both", expand=True, padx=pad, pady=(0, SPACE_SM))
        self._wall = wall
        ctk.CTkLabel(wall, text="HARI INI", font=FONT_LABEL, text_color=_WA_DAYPILL_TX,
                     fg_color=_WA_DAYPILL, corner_radius=RADIUS_SM, width=72, height=18
                     ).pack(pady=(SPACE_SM, SPACE_XS))
        self._preview = ctk.CTkTextbox(wall, fg_color=_WA_BUBBLE, text_color=_WA_BUBBLE_TX,
                                       corner_radius=RADIUS_MD, font=FONT_BODY, wrap="word",
                                       height=196)
        self._preview.pack(fill="both", expand=True, padx=(46, SPACE_MD), pady=(0, SPACE_XS))
        stamp = ctk.CTkFrame(wall, fg_color="transparent")
        stamp.pack(anchor="e", padx=(0, SPACE_MD), pady=(0, SPACE_SM))
        ctk.CTkLabel(stamp, text=datetime.now().strftime("%H:%M"), font=FONT_MONO_SMALL,
                     text_color=_WA_DAYPILL_TX).pack(side="left")
        ctk.CTkLabel(stamp, text="✓✓", font=FONT_MONO_SMALL, text_color=_WA_TICK
                     ).pack(side="left", padx=(SPACE_XS, 0))

        # actions
        actions = ctk.CTkFrame(self.right, fg_color="transparent")
        actions.pack(fill="x", padx=pad, pady=(0, pad))
        self._send_btn = ctk.CTkButton(
            actions, text="🟢  Kirim via WhatsApp", fg_color=_WA_SEND,
            hover_color=_WA_SEND_HOVER, text_color="#05231C", font=FONT_BODY_BOLD,
            command=self._kirim, state=("normal" if phone else "disabled"))
        self._send_btn.pack(side="left")
        ctk.CTkButton(actions, text="📋 Salin teks", fg_color="transparent",
                      border_width=1, border_color=COLOR_BORDER_STRONG, text_color=COLOR_TEXT,
                      hover_color=COLOR_SURFACE_HIGH, font=FONT_BODY, command=self._salin
                      ).pack(side="left", padx=(SPACE_SM, 0))
        if not phone:
            ctk.CTkLabel(actions, text="(atur nomor di data pegawai)", font=FONT_MONO_SMALL,
                         text_color=COLOR_TEXT_DISABLED).pack(side="left", padx=(SPACE_SM, 0))
        self._contact_btn = ctk.CTkButton(actions, text="", width=176, font=FONT_SMALL,
                                          command=self._toggle_contacted)
        self._contact_btn.pack(side="right")
        self._render_contact_btn(contacted)

        self._regen()

    # ---- actions ----------------------------------------------------------
    def _regen(self):
        if not self._preview:
            return
        text = build_wa_message(self._emp["nama"], self._current_month, self._issues,
                                self._officer, tone=self._tone, note=self._note)
        self._preview.delete("1.0", "end")
        self._preview.insert("1.0", text)

    def _on_tone(self, value):
        self._tone = _TONE_LABELS.get(value, "formal")
        self._regen()

    def _toggle_note(self):
        if self._note_visible:
            self._note_box.pack_forget()
            self._note_visible = False
            self._note_btn.configure(text="＋ Catatan")
        else:
            self._note_box.pack(fill="x", padx=SPACE_LG, pady=(0, SPACE_SM),
                                before=self._wall)
            self._note_visible = True
            self._note_btn.configure(text="－ Catatan")
            self._note_box.focus_set()

    def _on_note(self):
        self._note = self._note_box.get("1.0", "end").strip()
        self._regen()

    def _kirim(self):
        text = self._preview.get("1.0", "end").strip()
        url = wa_me_url((self._emp.get("phone") or "").strip(), text)
        if not url:
            messagebox.showwarning("Nomor tidak valid",
                                   "Nomor WhatsApp pegawai belum diset atau tidak valid.")
            return
        webbrowser.open(url)

    def _salin(self):
        pyperclip.copy(self._preview.get("1.0", "end").strip())
        messagebox.showinfo("Tersalin", "Teks pesan sudah masuk clipboard.")

    def _render_contact_btn(self, contacted):
        if contacted:
            self._contact_btn.configure(
                text="✓ Sudah dihubungi", fg_color=COLOR_SURFACE_HIGH,
                hover_color=COLOR_SURFACE_HIGH, text_color=COLOR_SUCCESS,
                border_width=1, border_color=COLOR_SUCCESS)
        else:
            self._contact_btn.configure(
                text="✓ Tandai sudah dihubungi", fg_color="transparent",
                hover_color=COLOR_SURFACE_HIGH, text_color=COLOR_TEXT_DIM,
                border_width=1, border_color=COLOR_BORDER_STRONG)

    def _toggle_contacted(self):
        emp_id = self._current_employee_id
        with get_connection(DB_PATH) as conn:
            if is_contacted(conn, employee_id=emp_id, year_month=self._current_month):
                unmark_contacted(conn, employee_id=emp_id, year_month=self._current_month)
                now_c = False
            else:
                mark_contacted(conn, employee_id=emp_id, year_month=self._current_month)
                now_c = True
        self._render_contact_btn(now_c)
        self._reload()
