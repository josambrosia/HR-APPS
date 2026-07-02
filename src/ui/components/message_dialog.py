"""Dark modal message dialog — replacement for tkinter.messagebox.

The stock messagebox renders as a light-gray Win32 dialog that clashes
with the dark JTS theme. This CTkToplevel matches the app: dark surface
card + subtle border, a small colored glyph as the kind cue (info cyan /
warning amber / error red / question magenta), wrapped message text and
themed buttons.

Follows the established dialog idioms (print_dialog / about_dialog):
transient parent, 50ms-deferred grab_set, screen-centered geometry,
Escape closes. Enter triggers the primary button.

Screens normally use the wrappers in src.ui.feedback (show_info /
show_warning / show_error / ask_yes_no) instead of this class directly.
"""
import customtkinter as ctk

from src.ui.theme import (
    FONT_FAMILY,
    COLOR_BG, COLOR_SURFACE, COLOR_SURFACE_HIGH,
    COLOR_BORDER, COLOR_BORDER_STRONG,
    COLOR_ACCENT, COLOR_ACCENT_HOVER,
    COLOR_INFO, COLOR_WARN, COLOR_ERROR,
    COLOR_TEXT, COLOR_TEXT_DIM,
    FONT_HEADING, FONT_BODY, FONT_BODY_BOLD,
    SPACE_SM, SPACE_MD, SPACE_LG, SPACE_XL,
    RADIUS_MD, RADIUS_LG,
)


DIALOG_W = 460
_MIN_H = 150
_SCREEN_BUFFER = 100  # taskbar + title bar buffer

# kind → (glyph, accent color). Semantic mapping mirrors the toast variants.
_KIND_META = {
    "info":     ("ⓘ", COLOR_INFO),
    "warning":  ("⚠", COLOR_WARN),
    "error":    ("✕", COLOR_ERROR),
    "question": ("?", COLOR_ACCENT),
}


class MessageDialog(ctk.CTkToplevel):
    """Modal dialog with 1 or 2 buttons. Result readable after close.

    Args:
        parent: any widget — the dialog transients to its toplevel
        title: window title + heading text
        message: body text (wrapped)
        kind: "info" | "warning" | "error" | "question" — accent cue
        primary_text: right (accent) button text, triggered by Enter
        secondary_text: optional neutral button left of primary; None = 1-button

    Attributes:
        result: True if the primary button closed the dialog, False if
            secondary / Escape / window close. Read it after wait_window().
    """

    def __init__(
        self, parent, title: str, message: str, *,
        kind: str = "info",
        primary_text: str = "OK",
        secondary_text: str | None = None,
    ):
        super().__init__(parent)
        self.result = False
        self.title(title)
        self.resizable(False, False)
        self.configure(fg_color=COLOR_BG)
        self.transient(parent.winfo_toplevel())

        glyph, accent = _KIND_META.get(kind, _KIND_META["info"])
        self._build(title, message, glyph, accent, primary_text, secondary_text)

        # Size to content (message length varies), center on SCREEN,
        # clamp height like the other dialogs.
        self.update_idletasks()
        sh = self.winfo_screenheight()
        sw = self.winfo_screenwidth()
        w = DIALOG_W
        h = min(max(self.winfo_reqheight(), _MIN_H), sh - _SCREEN_BUFFER)
        x = (sw - w) // 2
        y = max(0, (sh - h) // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

        self.after(50, self._deferred_grab)
        self.bind("<Escape>", lambda _e: self._on_cancel())
        self.bind("<Return>", lambda _e: self._on_primary())
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

    def _build(
        self, title: str, message: str, glyph: str, accent: str,
        primary_text: str, secondary_text: str | None,
    ):
        card = ctk.CTkFrame(
            self, fg_color=COLOR_SURFACE,
            border_width=1, border_color=COLOR_BORDER,
            corner_radius=RADIUS_LG,
        )
        card.pack(fill="both", expand=True, padx=SPACE_SM, pady=SPACE_SM)

        # Header: colored kind glyph + title
        head = ctk.CTkFrame(card, fg_color="transparent")
        head.pack(fill="x", padx=SPACE_XL, pady=(SPACE_LG, SPACE_SM))
        ctk.CTkLabel(
            head, text=glyph,
            font=(FONT_FAMILY, 18, "bold"),
            text_color=accent,
        ).pack(side="left")
        ctk.CTkLabel(
            head, text=title,
            font=FONT_HEADING, text_color=COLOR_TEXT,
            anchor="w",
        ).pack(side="left", padx=(SPACE_SM, 0))

        # Message (wrapped)
        ctk.CTkLabel(
            card, text=message,
            font=FONT_BODY, text_color=COLOR_TEXT_DIM,
            wraplength=DIALOG_W - 2 * (SPACE_XL + SPACE_SM),
            justify="left", anchor="w",
        ).pack(fill="x", padx=SPACE_XL, pady=(0, SPACE_MD))

        # Buttons — primary packed first so it lands far right (CTA idiom)
        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(fill="x", padx=SPACE_XL, pady=(SPACE_SM, SPACE_LG), side="bottom")
        self.primary_button = ctk.CTkButton(
            btn_row, text=primary_text, command=self._on_primary,
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
            text_color=COLOR_BG,
            width=110, height=36,
            font=FONT_BODY_BOLD,
            corner_radius=RADIUS_MD,
        )
        self.primary_button.pack(side="right")
        self.secondary_button = None
        if secondary_text is not None:
            self.secondary_button = ctk.CTkButton(
                btn_row, text=secondary_text, command=self._on_cancel,
                fg_color="transparent",
                border_width=1, border_color=COLOR_BORDER_STRONG,
                text_color=COLOR_TEXT_DIM,
                hover_color=COLOR_SURFACE_HIGH,
                width=100, height=36,
                font=FONT_BODY_BOLD,
                corner_radius=RADIUS_MD,
            )
            self.secondary_button.pack(side="right", padx=(0, SPACE_MD))

    def _deferred_grab(self):
        """Grab AFTER the window is ready (otherwise grab fails). Guarded so
        the 50ms timer firing after an early destroy() is a silent no-op."""
        try:
            if not self.winfo_exists():
                return
            self.grab_set()
            self.focus_set()
        except Exception:
            pass

    def _close(self, result: bool):
        self.result = result
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()

    def _on_primary(self):
        self._close(True)

    def _on_cancel(self):
        self._close(False)
