# tests/test_tree_hover.py
"""Item 15 — hover baris Treeview (satu implementasi, dipakai semua layar)."""
from tkinter import ttk

from src.ui.components.tree_style import RowHover, HOVER_TAG, style_treeview


def _tree(tk_root):
    style_treeview("Hov.Treeview")
    t = ttk.Treeview(tk_root, style="Hov.Treeview", columns=("a",),
                     show="tree headings", height=4)
    for i in range(4):
        t.insert("", "end", iid=str(i), text=f"Pegawai {i}", values=(i,))
    t.pack()
    return t


def test_hover_menandai_baris_di_bawah_kursor(tk_root):
    t = _tree(tk_root)
    try:
        RowHover(t)
        t._row_hover._apply("2")
        assert HOVER_TAG in t.item("2", "tags")
    finally:
        t.destroy()


def test_pindah_baris_melepas_tanda_dari_baris_sebelumnya(tk_root):
    t = _tree(tk_root)
    try:
        RowHover(t)
        t._row_hover._apply("1")
        t._row_hover._apply("3")
        assert HOVER_TAG not in t.item("1", "tags")
        assert HOVER_TAG in t.item("3", "tags")
    finally:
        t.destroy()


def test_keluar_dari_tabel_membersihkan_tanda(tk_root):
    t = _tree(tk_root)
    try:
        RowHover(t)
        t._row_hover._apply("1")
        t._row_hover._apply(None)
        assert HOVER_TAG not in t.item("1", "tags")
    finally:
        t.destroy()


def test_tag_zebra_tidak_hilang_setelah_hover(tk_root):
    """Regresi: baris zebra harus kembali ke tag semula, bukan kehilangannya."""
    t = _tree(tk_root)
    try:
        t.item("1", tags=("evenrow",))
        RowHover(t)
        t._row_hover._apply("1")
        t._row_hover._apply(None)
        assert "evenrow" in t.item("1", "tags")
    finally:
        t.destroy()


def test_baris_lenyap_saat_disorot_tidak_meledak(tk_root):
    """Daftar sering dibangun ulang total setelah aksi; baris yang sedang
    disorot bisa lenyap di tengah jalan."""
    t = _tree(tk_root)
    try:
        RowHover(t)
        t._row_hover._apply("1")
        t.delete("1")
        t._row_hover._apply("2")      # tidak boleh melempar TclError
        assert HOVER_TAG in t.item("2", "tags")
    finally:
        t.destroy()
