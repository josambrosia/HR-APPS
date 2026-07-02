"""Dark-themed feedback dialogs — drop-in replacement for tkinter.messagebox.

Usage (same shape as messagebox — blocks until the user closes):

    from src.ui import feedback

    feedback.show_error(self, "Error parsing", str(e))
    feedback.show_warning(self, "File kosong", "Tidak ada baris ...")
    feedback.show_info(self, "Selesai", "Laporan tersimpan.")
    if feedback.ask_yes_no(self, "Hapus data?", "Tindakan ini permanen."):
        ...

`parent` may be any widget — the dialog transients to its toplevel. All
four functions block via wait_window (messagebox semantics); ask_yes_no
returns True only when the user clicks the yes button (Enter counts),
False on "Batal", Escape, or window close.
"""
from src.ui.components.message_dialog import MessageDialog


def _show(
    parent, title: str, message: str, *,
    kind: str, primary_text: str = "OK", secondary_text: str | None = None,
) -> bool:
    dialog = MessageDialog(
        parent, title, message,
        kind=kind, primary_text=primary_text, secondary_text=secondary_text,
    )
    dialog.wait_window()
    return dialog.result


def show_info(parent, title: str, message: str) -> None:
    """Cyan info dialog — pengganti messagebox.showinfo."""
    _show(parent, title, message, kind="info")


def show_warning(parent, title: str, message: str) -> None:
    """Amber warning dialog — pengganti messagebox.showwarning."""
    _show(parent, title, message, kind="warning")


def show_error(parent, title: str, message: str) -> None:
    """Red error dialog — pengganti messagebox.showerror."""
    _show(parent, title, message, kind="error")


def ask_yes_no(
    parent, title: str, message: str,
    yes_text: str = "Ya", no_text: str = "Batal",
) -> bool:
    """Confirmation dialog — pengganti messagebox.askyesno.

    Returns True on yes (Enter counts), False on Batal / Escape / close.
    """
    return _show(
        parent, title, message,
        kind="question", primary_text=yes_text, secondary_text=no_text,
    )
