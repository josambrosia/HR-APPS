import webbrowser
from datetime import datetime

import customtkinter as ctk
import pyperclip

from src.config import DB_PATH
from src.db.attendance import (
    list_employees_with_open_issues, list_open_issues_for_employee,
)
from src.db.connection import get_connection
from src.db.employees import get_employee_by_id
from src.db.settings import get_setting
from src.db.wa_contacts import (
    contacted_map, is_contacted, mark_contacted, unmark_contacted,
)
from src.core.week_utils import full_month_range
from src.core.wa_message import build_wa_message, format_issue, wa_me_url
from src.ui import feedback
from src.ui.components.search_bar import SearchBar
from src.ui.components.toast import show_success_toast
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

# Debounce for the name filter — same rationale as resolve_base: a burst
# of keystrokes re-renders the employee list once, not once per key.
SEARCH_DEBOUNCE_MS = 200

_EMPTY_PANEL_MSG = "Pilih pegawai di kiri untuk menyusun pesan"


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
        self._search_query = ""
        self._build()
        self._reload()
        # Search shortcuts (Ctrl+F focus + click-outside blur) live in the
        # SearchBar component so the corrected focus logic is shared, not
        # copy-pasted across screens.
        self._search.install_shortcuts(self)

    # ---- layout -----------------------------------------------------------
    def _build(self):
        left = ctk.CTkFrame(self, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, SPACE_MD))
        left.grid_rowconfigure(2, weight=1)
        left.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(left, text="Pegawai · open issues", font=FONT_SUBHEAD,
                     text_color=COLOR_TEXT).grid(row=0, column=0, sticky="w",
                                                 pady=(0, SPACE_SM))
        # Shared SearchBar (debounced) — replaces the hand-rolled Entry +
        # StringVar-trace this screen carried pre-v22. Filter semantics are
        # unchanged: case-insensitive substring match on nama only.
        # width=170 keeps entry + clear + "N dari M" inside the 288px column.
        self._search = SearchBar(
            left, on_change=self._apply_filter, placeholder="🔍 Cari nama…",
            width=170, debounce_ms=SEARCH_DEBOUNCE_MS,
        )
        self._search.grid(row=1, column=0, sticky="ew", pady=(0, SPACE_SM))

        self.list_frame = ctk.CTkScrollableFrame(left, fg_color=COLOR_SURFACE,
                                                 corner_radius=RADIUS_MD)
        self.list_frame.grid(row=2, column=0, sticky="nsew")

        right = ctk.CTkFrame(self, fg_color=COLOR_SURFACE, border_width=1,
                             border_color=COLOR_BORDER, corner_radius=RADIUS_MD)
        right.grid(row=0, column=1, sticky="nsew")
        self.right = right
        self._show_empty(_EMPTY_PANEL_MSG)

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
            self._rows_cache = list_employees_with_open_issues(conn, start, end)
            self._contacted = contacted_map(conn, month)
        self._render_list()

    def on_show(self):
        """Shell contract — called by the app shell every time this cached
        screen is re-displayed (NOT after first construction).

        Re-reads the active month + employee list (open-issue counts change
        when issues are resolved on other screens) while preserving the
        typed search query, then re-renders the selected employee's compose
        panel with fresh issue data and a re-read 'sudah dihubungi' mark.
        If the selected employee no longer has open issues, the right panel
        falls back to the placeholder. Idempotent; empty DB / no active
        month behaves exactly like __init__.
        """
        self._reload()
        emp_id = self._current_employee_id
        if emp_id is None:
            return
        if any(r["id"] == emp_id for r in self._rows_cache):
            self._show_for(emp_id)
        else:
            self._current_employee_id = None
            self._show_empty(_EMPTY_PANEL_MSG)

    def _apply_filter(self, query: str):
        # Skip the list rebuild when the EFFECTIVE query (matching is
        # case/whitespace-insensitive) didn't change — the debounced
        # KeyRelease also fires for modifier/navigation keys.
        if query.lower().strip() == self._search_query.lower().strip():
            self._search_query = query
            return
        self._search_query = query
        self._render_list()

    def _render_list(self, empty_msg="(tidak ada open issue)"):
        if not hasattr(self, "list_frame"):
            return
        for w in self.list_frame.winfo_children():
            w.destroy()
        q = self._search_query.strip().lower()
        rows = [r for r in self._rows_cache if q in r["nama"].lower()]
        self._search.set_count(len(rows), len(self._rows_cache))
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
            emp = get_employee_by_id(conn, emp_id)
            start, end = full_month_range(self._current_month)
            issues = list_open_issues_for_employee(conn, emp_id, start, end)
            self._officer = (get_setting(conn, "hr_officer_name") or "").strip()
            contacted = is_contacted(conn, employee_id=emp_id,
                                     year_month=self._current_month)
        if not emp or not issues:
            self._show_empty("(tidak ada open issue)")
            return
        self._emp = dict(emp)
        self._issues = issues
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
            feedback.show_warning(
                self, "Nomor tidak valid",
                "Nomor WhatsApp pegawai belum diset atau tidak valid.")
            return
        webbrowser.open(url)

    def _salin(self):
        pyperclip.copy(self._preview.get("1.0", "end").strip())
        show_success_toast(
            self.winfo_toplevel(), title="Tersalin",
            message="Teks pesan sudah masuk clipboard.")

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
