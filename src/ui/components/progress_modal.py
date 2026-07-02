"""Shared progress overlay modal — reusable for long operations.

Usage (sync loop on the main thread — legacy style):
    with ProgressModal(parent, title="Memproses file") as p:
        p.update_progress(0.0, "Parsing...")
        # ... work ...
        p.update_progress(0.5, "Inserting rows...")
        # ... more work ...
        p.update_progress(1.0, "Selesai")

update_progress() pumps Tk's single-threaded update() so the bar
repaints while the main loop is blocked by the work loop.

Usage (async — run_bg flows, main loop stays free):
    modal = ProgressModal(parent, title="Memproses Import")
    modal.open()
    # on_progress (main thread) → modal.set_progress(done / total, "...")
    # on_done / on_error       → modal.close()

set_progress() does NOT pump the event loop — with run_bg the main loop
is already free, so widgets repaint on the next idle by themselves.
"""
import customtkinter as ctk

from src.ui.theme import (
    COLOR_BG, COLOR_SURFACE, COLOR_BORDER,
    COLOR_ACCENT, COLOR_TEXT, COLOR_TEXT_MUTED,
    FONT_HEADING, FONT_BODY,
    SPACE_MD, SPACE_LG,
    RADIUS_LG,
)


class ProgressModal:
    """Context-manager wrapper around a CTkToplevel progress overlay."""

    def __init__(self, parent, title: str = "Memproses..."):
        self.parent = parent
        self.title = title
        self.window = None

    def __enter__(self):
        self.window = ctk.CTkToplevel(self.parent)
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.configure(fg_color=COLOR_BG)

        # Size + center
        w, h = 400, 140
        self.window.update_idletasks()
        x = (self.window.winfo_screenwidth() - w) // 2
        y = (self.window.winfo_screenheight() - h) // 2
        self.window.geometry(f"{w}x{h}+{x}+{y}")

        # Make modal: block input to parent during long operation
        self.window.transient(self.parent)
        self.window.grab_set()

        # Card frame inside for border
        card = ctk.CTkFrame(
            self.window, fg_color=COLOR_SURFACE,
            border_width=1, border_color=COLOR_BORDER,
            corner_radius=RADIUS_LG,
        )
        card.pack(fill="both", expand=True, padx=4, pady=4)

        # Title
        ctk.CTkLabel(
            card, text=self.title,
            font=FONT_HEADING, text_color=COLOR_TEXT,
        ).pack(pady=(SPACE_LG, SPACE_MD), padx=SPACE_LG, anchor="w")

        # Status text (updateable)
        self.status_lbl = ctk.CTkLabel(
            card, text="...",
            font=FONT_BODY, text_color=COLOR_TEXT_MUTED,
        )
        self.status_lbl.pack(pady=(0, SPACE_MD), padx=SPACE_LG, anchor="w")

        # Progress bar
        self.bar = ctk.CTkProgressBar(
            card, width=320, height=6, corner_radius=3,
            progress_color=COLOR_ACCENT,
            fg_color=COLOR_BORDER,
        )
        self.bar.pack(pady=(0, SPACE_LG), padx=SPACE_LG, anchor="w")
        self.bar.set(0)

        self.window.update()
        return self

    def open(self):
        """Show the modal outside a `with` block (async run_bg flows)."""
        return self.__enter__()

    def close(self):
        """Destroy a modal shown via open(). Safe to call when closed."""
        self.__exit__(None, None, None)

    def update_progress(self, pct: float, status: str):
        """Set progress bar (0.0-1.0) and status text. Forces redraw —
        for sync loops that block the main loop between calls."""
        if self.window is None:
            return
        self.bar.set(max(0.0, min(1.0, pct)))
        self.status_lbl.configure(text=status)
        self.window.update()

    def set_progress(self, pct: float, status: str):
        """Set progress bar (0.0-1.0) and status text WITHOUT pumping the
        event loop — for async flows (run_bg on_progress callbacks) where
        the main loop is free and update() would re-enter it mid-callback."""
        if self.window is None:
            return
        self.bar.set(max(0.0, min(1.0, pct)))
        self.status_lbl.configure(text=status)

    def __exit__(self, *args):
        if self.window is not None:
            try:
                self.window.grab_release()
            except Exception:
                pass
            try:
                self.window.destroy()
            except Exception:
                pass
            self.window = None
