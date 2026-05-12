import webbrowser
import customtkinter as ctk
import pyperclip
from tkinter import messagebox

from src.config import DB_PATH
from src.db.connection import get_connection
from src.core.issue_summary import render_summary_for_employee
from src.ui.theme import (
    FONT_MONO,
    COLOR_BG, COLOR_SURFACE, COLOR_SURFACE_HIGH,
    COLOR_BORDER,
    COLOR_ACCENT, COLOR_ACCENT_HOVER,
    COLOR_INFO, COLOR_WARN,
    COLOR_TEXT, COLOR_TEXT_MUTED, COLOR_TEXT_DISABLED,
    FONT_SUBHEAD,
    FONT_BODY, FONT_BODY_BOLD,
    FONT_MONO_SMALL,
    SPACE_XS, SPACE_SM, SPACE_MD, SPACE_LG,
    RADIUS_MD,
)


class WhatsAppAssistantScreen(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(0, weight=1)
        # Track the currently displayed employee so the WA Web button can
        # be rebuilt per selection (employees may or may not have phone).
        self._current_employee_id: int | None = None
        self._build()
        self._reload()

    def _build(self):
        left = ctk.CTkFrame(self, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, SPACE_MD))
        ctk.CTkLabel(left, text="Pegawai (open issues)",
                     font=FONT_SUBHEAD,
                     text_color=COLOR_TEXT).pack(anchor="w", pady=(0, SPACE_SM))
        self.list_frame = ctk.CTkScrollableFrame(
            left, fg_color=COLOR_SURFACE,
            corner_radius=RADIUS_MD,
        )
        self.list_frame.pack(fill="both", expand=True)

        right = ctk.CTkFrame(
            self, fg_color=COLOR_SURFACE,
            border_width=1, border_color=COLOR_BORDER,
            corner_radius=RADIUS_MD,
        )
        right.grid(row=0, column=1, sticky="nsew")
        self.right = right
        ctk.CTkLabel(self.right, text="Pilih pegawai di kiri",
                     font=FONT_BODY,
                     text_color=COLOR_TEXT_MUTED).pack(pady=80)

    def _reload(self):
        for w in self.list_frame.winfo_children():
            w.destroy()
        with get_connection(DB_PATH) as conn:
            rows = conn.execute(
                """
                SELECT e.id, e.nama, COUNT(*) AS open_cnt
                  FROM attendance_records ar
                  JOIN employees e ON ar.employee_id = e.id
                 WHERE ar.has_issue = 1 AND ar.reason_category IS NULL
                 GROUP BY e.id
                 ORDER BY e.nama
                """
            ).fetchall()
        if not rows:
            ctk.CTkLabel(self.list_frame, text="(tidak ada open issue)",
                         font=FONT_BODY,
                         text_color=COLOR_TEXT_MUTED).pack(pady=20)
            return
        for r in rows:
            row_frame = ctk.CTkFrame(self.list_frame, fg_color="transparent")
            row_frame.pack(fill="x", padx=SPACE_XS, pady=2)
            # Whole row is a button so the whole strip is clickable; the
            # rose count badge sits at the right edge.
            btn = ctk.CTkButton(
                row_frame, text=r["nama"],
                anchor="w",
                fg_color="transparent",
                hover_color=COLOR_SURFACE_HIGH,
                text_color=COLOR_TEXT,
                font=FONT_BODY,
                command=lambda emp_id=r["id"]: self._show_for(emp_id),
            )
            btn.pack(side="left", fill="x", expand=True)
            # Rose badge with open issue count.
            ctk.CTkLabel(
                row_frame, text=str(r["open_cnt"]),
                fg_color=COLOR_WARN, text_color=COLOR_TEXT,
                font=FONT_MONO_SMALL,
                corner_radius=RADIUS_MD,
                width=28, height=20,
            ).pack(side="right", padx=(SPACE_XS, SPACE_SM))

    def _open_wa_web(self, phone: str):
        """Convert phone to wa.me URL and open in default browser.

        Indonesian phone format handling:
        - '08123...' → '628123...' (replace leading 0 with country code)
        - '+628...' or '628...' → '628...' (digits only, country code kept)

        Validates digit length (10-15 per E.164 standard) before opening URL.
        If invalid, shows warning dialog instead.
        """
        digits = "".join(c for c in phone if c.isdigit())
        if digits.startswith("0"):
            digits = "62" + digits[1:]

        if len(digits) < 10 or len(digits) > 15:
            messagebox.showwarning(
                "Format Nomor Tidak Valid",
                f"Nomor '{phone}' tidak valid (perlu 10-15 digit setelah normalisasi).\n"
                f"Format yang diterima: 08xxxxxxxx atau 628xxxxxxxx.",
            )
            return

        webbrowser.open(f"https://wa.me/{digits}")

    def _show_for(self, emp_id: int):
        self._current_employee_id = emp_id
        for w in self.right.winfo_children():
            w.destroy()
        with get_connection(DB_PATH) as conn:
            text = render_summary_for_employee(conn, emp_id)
            row = conn.execute(
                "SELECT phone FROM employees WHERE id = ?", (emp_id,)
            ).fetchone()
            phone_str = (row["phone"] or "").strip() if row else ""
        has_phone = bool(phone_str)
        if not text:
            ctk.CTkLabel(self.right, text="(tidak ada open issue)",
                         font=FONT_BODY,
                         text_color=COLOR_TEXT_MUTED).pack(pady=80)
            return

        # Terminal-style mono output box. Darker than the surrounding
        # panel (COLOR_BG) so it reads like a dev tool's output pane.
        box = ctk.CTkTextbox(
            self.right,
            fg_color=COLOR_BG,
            border_width=1, border_color=COLOR_BORDER,
            corner_radius=RADIUS_MD,
            text_color=COLOR_TEXT,
            font=(FONT_MONO, 12),
            wrap="word",
        )
        box.pack(fill="both", expand=True, padx=SPACE_LG, pady=SPACE_LG)
        box.insert("1.0", text)
        box.configure(state="disabled")

        # Action buttons row.
        actions_frame = ctk.CTkFrame(self.right, fg_color="transparent")
        actions_frame.pack(fill="x", padx=SPACE_LG, pady=(0, SPACE_LG))

        # Copy — magenta primary CTA.
        self.copy_btn = ctk.CTkButton(
            actions_frame, text="📋 Copy ke Clipboard",
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
            text_color=COLOR_BG,
            font=FONT_BODY_BOLD,
            command=lambda t=text: self._copy(t),
        )
        self.copy_btn.pack(side="left")

        # Buka WA Web — cyan secondary, gracefully disabled when no phone.
        self.wa_web_btn = ctk.CTkButton(
            actions_frame,
            text="🟢 Buka WA Web",
            fg_color="transparent",
            border_width=1, border_color=COLOR_INFO,
            text_color=COLOR_INFO,
            hover_color=COLOR_SURFACE_HIGH,
            font=FONT_BODY_BOLD,
            state="normal" if has_phone else "disabled",
            command=(lambda p=phone_str: self._open_wa_web(p)) if has_phone else None,
        )
        self.wa_web_btn.pack(side="left", padx=(SPACE_SM, 0))

        if not has_phone:
            ctk.CTkLabel(
                actions_frame,
                text="(phone belum diset)",
                font=FONT_MONO_SMALL,
                text_color=COLOR_TEXT_DISABLED,
            ).pack(side="left", padx=(SPACE_SM, 0))

    def _copy(self, text: str):
        pyperclip.copy(text)
        messagebox.showinfo("Copied", "Teks sudah masuk clipboard.")
