"""Click-anywhere-to-dismiss modal toast for confirmations and alerts.

Use case: after an action completes, show a friendly confirmation that
doesn't require precision aim — the user can dismiss by clicking anywhere
on the popup, or pressing Esc / Enter.

Variants:
  - show_success_toast → emerald border + ✓ icon (default)
  - show_error_toast   → dark red border + ✗ icon
  - show_info_toast    → cyan border + i icon
"""
import customtkinter as ctk

from src.ui.theme import (
    FONT_FAMILY,
    COLOR_SURFACE,
    COLOR_INFO, COLOR_SUCCESS, COLOR_ERROR,
    COLOR_TEXT, COLOR_TEXT_DIM,
    FONT_HEADING, FONT_BODY,
    RADIUS_LG,
)


def _show_toast(
    parent,
    title: str,
    message: str,
    *,
    border_color: str,
    icon: str,
    icon_color: str,
) -> None:
    """Internal: render the toast modal with the given semantic styling."""
    toast = ctk.CTkToplevel(parent)
    toast.title(title)
    toast.geometry("480x220")
    toast.resizable(False, False)
    toast.configure(fg_color=COLOR_SURFACE)
    toast.transient(parent)

    # Center on parent
    parent.update_idletasks()
    px = parent.winfo_rootx()
    py = parent.winfo_rooty()
    pw = parent.winfo_width()
    ph = parent.winfo_height()
    w, h = 480, 220
    x = px + (pw - w) // 2
    y = py + (ph - h) // 2
    toast.geometry(f"{w}x{h}+{x}+{y}")

    # Card with 2px semantic border for at-a-glance status recognition.
    card = ctk.CTkFrame(
        toast,
        fg_color=COLOR_SURFACE,
        border_width=2,
        border_color=border_color,
        corner_radius=RADIUS_LG,
    )
    card.pack(fill="both", expand=True, padx=8, pady=8)

    body = ctk.CTkFrame(card, fg_color="transparent")
    body.pack(fill="both", expand=True, padx=24, pady=20)

    ctk.CTkLabel(
        body, text=icon,
        font=(FONT_FAMILY, 48, "bold"),
        text_color=icon_color,
    ).pack(pady=(0, 4))

    ctk.CTkLabel(
        body, text=title,
        font=FONT_HEADING,
        text_color=COLOR_TEXT,
    ).pack(pady=(0, 8))

    ctk.CTkLabel(
        body, text=message,
        font=FONT_BODY,
        text_color=COLOR_TEXT_DIM,
        wraplength=400, justify="center",
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


def show_success_toast(parent, title: str, message: str) -> None:
    """Show a centered success modal — emerald border, checkmark icon."""
    _show_toast(
        parent, title, message,
        border_color=COLOR_SUCCESS,
        icon="✓",
        icon_color=COLOR_SUCCESS,
    )


def show_error_toast(parent, title: str, message: str) -> None:
    """Show a centered error modal — dark red border, X icon."""
    _show_toast(
        parent, title, message,
        border_color=COLOR_ERROR,
        icon="✗",
        icon_color=COLOR_ERROR,
    )


def show_info_toast(parent, title: str, message: str) -> None:
    """Show a centered info modal — cyan border, info icon."""
    _show_toast(
        parent, title, message,
        border_color=COLOR_INFO,
        icon="ⓘ",
        icon_color=COLOR_INFO,
    )
