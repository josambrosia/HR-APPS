"""Click-anywhere-to-dismiss modal toast for success confirmations.

Use case: after a long action completes successfully, show a friendly
confirmation that doesn't require precision aim — the user can dismiss
by clicking anywhere on the popup, or pressing Esc / Enter.
"""
import customtkinter as ctk

from src.ui.theme import (
    COLOR_PANEL, COLOR_OK, COLOR_TEXT, COLOR_TEXT_DIM, FONT_FAMILY,
)


def show_success_toast(parent, title: str, message: str) -> None:
    """Show a centered modal popup with a checkmark, title, and message.

    The entire popup is clickable: any mouse click within the toast
    (or pressing Esc / Enter) dismisses it. Blocks the parent window
    until dismissed.
    """
    toast = ctk.CTkToplevel(parent)
    toast.title(title)
    toast.geometry("420x220")
    toast.resizable(False, False)
    toast.configure(fg_color=COLOR_PANEL)
    toast.transient(parent)

    # Center on parent
    parent.update_idletasks()
    px = parent.winfo_rootx()
    py = parent.winfo_rooty()
    pw = parent.winfo_width()
    ph = parent.winfo_height()
    w, h = 420, 220
    x = px + (pw - w) // 2
    y = py + (ph - h) // 2
    toast.geometry(f"{w}x{h}+{x}+{y}")

    # Content
    body = ctk.CTkFrame(toast, fg_color="transparent")
    body.pack(fill="both", expand=True, padx=24, pady=20)

    ctk.CTkLabel(
        body, text="✓",
        font=(FONT_FAMILY, 48, "bold"),
        text_color=COLOR_OK,
    ).pack(pady=(0, 4))

    ctk.CTkLabel(
        body, text=title,
        font=(FONT_FAMILY, 16, "bold"),
        text_color=COLOR_TEXT,
    ).pack(pady=(0, 8))

    ctk.CTkLabel(
        body, text=message,
        font=(FONT_FAMILY, 12),
        text_color=COLOR_TEXT,
        wraplength=370, justify="center",
    ).pack(pady=(0, 12))

    ctk.CTkLabel(
        body, text="(klik di mana saja untuk tutup)",
        font=(FONT_FAMILY, 9, "italic"),
        text_color=COLOR_TEXT_DIM,
    ).pack()

    def dismiss(_event=None):
        try:
            toast.grab_release()
        except Exception:
            pass
        toast.destroy()

    # Bind click on every descendant
    def bind_all_clicks(widget):
        widget.bind("<Button-1>", dismiss)
        for child in widget.winfo_children():
            bind_all_clicks(child)

    bind_all_clicks(toast)
    toast.bind("<Escape>", dismiss)
    toast.bind("<Return>", dismiss)

    # Modal + focus, but grab AFTER window is ready (otherwise grab fails)
    toast.after(50, lambda: (toast.grab_set(), toast.focus_set()))
    toast.wait_window()
