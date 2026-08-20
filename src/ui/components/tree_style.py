"""Shared ttk.Treeview styling for the dark theme (v20)."""
from tkinter import ttk
import tkinter as tk

from src.ui.theme import (
    COLOR_SURFACE, COLOR_SURFACE_HIGH, COLOR_TEXT, COLOR_TEXT_MUTED,
    COLOR_BORDER, FONT_FAMILY, FONT_SMALL,
)

ZEBRA_EVEN = COLOR_SURFACE      # #141414
ZEBRA_ODD = "#181818"           # one subtle step lighter


def style_treeview(style_name: str, *, rowheight: int = 28) -> None:
    """Configure a ttk Treeview style consistently: taller rows, flat muted
    uppercase-ready header, clean selected state."""
    style = ttk.Style()
    try:
        style.theme_use("clam")
    except Exception:
        pass
    style.configure(
        style_name, background=COLOR_SURFACE, fieldbackground=COLOR_SURFACE,
        foreground=COLOR_TEXT, rowheight=rowheight, borderwidth=0, font=FONT_SMALL,
    )
    style.configure(
        f"{style_name}.Heading", background=COLOR_SURFACE_HIGH,
        foreground=COLOR_TEXT_MUTED, relief="flat", font=(FONT_FAMILY, 9, "bold"),
    )
    style.map(
        style_name,
        background=[("selected", COLOR_SURFACE_HIGH)],
        foreground=[("selected", COLOR_TEXT)],
    )


def apply_zebra_tags(tree: ttk.Treeview) -> None:
    """Configure odd/even row background tags. Caller passes
    tags=("evenrow",) / ("oddrow",) alternately on insert."""
    tree.tag_configure("evenrow", background=ZEBRA_EVEN)
    tree.tag_configure("oddrow", background=ZEBRA_ODD)


HOVER_TAG = "rowhover"


class RowHover:
    """Menyorot baris di bawah kursor.

    ttk.Treeview tidak punya state hover di style.map (style_treeview hanya
    memetakan 'selected'), jadi tabel yang jelas interaktif tidak bereaksi
    sama sekali terhadap kursor. Ini menambalnya lewat <Motion> +
    identify_row + tag.

    Tanpa animasi: warna baris berpindah dalam satu frame. Menganimasikannya
    berarti men-tween tag_configure (9,83 ms/frame) pada setiap gerakan mouse
    — terlalu mahal untuk imbalannya. Kilat baris (item 10) memang memakai
    tween tag, tapi hanya sekali per aksi, bukan per piksel gerakan.
    """

    def __init__(self, tree: ttk.Treeview):
        self.tree = tree
        self._current = None
        tree.tag_configure(HOVER_TAG, background=COLOR_SURFACE_HIGH)
        tree.bind("<Motion>", self._on_motion, add="+")
        tree.bind("<Leave>", lambda _e: self._apply(None), add="+")
        tree._row_hover = self          # pegangan untuk tes & pembersihan

    def _on_motion(self, event):
        self._apply(self.tree.identify_row(event.y) or None)

    def _apply(self, iid):
        if iid == self._current:
            return
        if self._current:
            self._set_tags(self._current, add=False)
        self._current = iid
        if iid:
            self._set_tags(iid, add=True)

    def _set_tags(self, iid, *, add: bool):
        try:
            tags = [t for t in self.tree.item(iid, "tags") if t != HOVER_TAG]
        except tk.TclError:
            return                      # baris sudah lenyap saat daftar dibangun ulang
        if add:
            tags.append(HOVER_TAG)
        self.tree.item(iid, tags=tuple(tags))


class CellTooltip:
    """Hover tooltip showing the full text of one column's cell — for columns
    whose content gets truncated (e.g. Alasan). Bind once per tree."""

    def __init__(self, tree: ttk.Treeview, column_name: str):
        self.tree = tree
        self.column_name = column_name
        self.tip = None
        self._last = None
        tree.bind("<Motion>", self._on_motion, add="+")
        tree.bind("<Leave>", lambda _e: self._hide(), add="+")

    def _col_index(self):
        cols = list(self.tree["columns"])
        return cols.index(self.column_name) if self.column_name in cols else -1

    def _on_motion(self, event):
        row = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)  # "#N" 1-based display index
        idx = self._col_index()
        if not row or idx < 0 or col != f"#{idx + 1}":
            self._hide(); return
        text = self.tree.set(row, self.column_name)
        if not text or text == "-":
            self._hide(); return
        if self._last == (row, col):
            return
        self._last = (row, col)
        self._hide()
        self.tip = tk.Toplevel(self.tree)
        self.tip.wm_overrideredirect(True)
        self.tip.configure(bg=COLOR_BORDER)
        tk.Label(self.tip, text=text, bg=COLOR_SURFACE_HIGH, fg=COLOR_TEXT,
                 font=FONT_SMALL, justify="left", padx=8, pady=4).pack(padx=1, pady=1)
        self.tip.wm_geometry(f"+{event.x_root + 14}+{event.y_root + 12}")

    def _hide(self):
        self._last = None
        if self.tip is not None:
            try:
                self.tip.destroy()
            except Exception:
                pass
            self.tip = None
