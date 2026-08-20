"""Item 13 — pil aktif meluncur di WeekNavBar dan segmented button."""
import tkinter as tk

import customtkinter as ctk

from src.ui import motion
from src.ui.components.week_nav import WeekNavBar
from src.ui.theme import COLOR_ACCENT, COLOR_BG


def _bar(tk_root, initial="semua"):
    return WeekNavBar(tk_root, current_month="2026-07",
                      on_change=lambda k: None, initial=initial)


def test_pilnya_tk_frame_bukan_ctk(tk_root):
    """tk.Frame, bukan CTkFrame — lihat pelajaran DPI item 02."""
    bar = _bar(tk_root)
    try:
        assert isinstance(bar._pill, tk.Frame)
        assert not isinstance(bar._pill, ctk.CTkFrame)
    finally:
        bar.destroy()


def test_pil_mendarat_tepat_di_tombol_aktif(tk_root):
    motion.set_enabled(False)
    bar = _bar(tk_root)
    bar.pack()
    tk_root.deiconify()
    tk_root.update()
    try:
        bar.set_active("minggu_2")
        tk_root.update()
        btn = bar._buttons["minggu_2"]
        assert bar._pill.winfo_x() == btn.winfo_x()
        assert bar._pill.winfo_width() == btn.winfo_width()
    finally:
        tk_root.withdraw()
        bar.destroy()


def test_pil_ikut_berpindah_saat_ganti_tombol(tk_root):
    motion.set_enabled(False)
    bar = _bar(tk_root)
    bar.pack()
    tk_root.deiconify()
    tk_root.update()
    try:
        bar.set_active("minggu_1")
        tk_root.update()
        x1 = bar._pill.winfo_x()
        bar.set_active("minggu_4")
        tk_root.update()
        x2 = bar._pill.winfo_x()
        assert x2 != x1
        assert x2 == bar._buttons["minggu_4"].winfo_x()
    finally:
        tk_root.withdraw()
        bar.destroy()


def test_penempatan_PERTAMA_saat_startup_sudah_tepat(tk_root):
    """Regresi DPI item 02: penempatan pertama memakai place(), bukan
    place_configure(). Kalau pil-nya CTkFrame, yang ini meleset ~76px di
    layar 125% sementara tampak normal di layar 100%.

    Penempatan pertama itu terjadi SAAT KONSTRUKSI (lewat after_idle), bukan
    saat klik pertama — supaya perpindahan periode pertama sudah meluncur,
    sama seperti garis sidebar.
    """
    motion.set_enabled(False)
    bar = _bar(tk_root, initial="minggu_3")
    bar.pack()
    tk_root.deiconify()
    tk_root.update()                 # jalankan after_idle + layout
    try:
        btn = bar._buttons["minggu_3"]
        assert bar._pill.winfo_ismapped(),             "pil belum terpasang setelah konstruksi — transisi pertama tidak akan meluncur"
        assert bar._pill.winfo_x() == btn.winfo_x()
        assert bar._pill.winfo_width() == btn.winfo_width()
    finally:
        tk_root.withdraw()
        bar.destroy()


def test_transisi_PERTAMA_sudah_meluncur(tk_root):
    """Konsekuensi dari tes di atas: karena pil sudah terpasang sejak startup,
    klik pertama menempuh jalur place_configure (meluncur), bukan jalur
    place() langsung."""
    motion.set_enabled(False)
    bar = _bar(tk_root, initial="semua")
    bar.pack()
    tk_root.deiconify()
    tk_root.update()
    try:
        assert bar._pill.winfo_ismapped(), "prasyarat: pil sudah terpasang"
        bar.set_active("minggu_4")
        tk_root.update()
        assert bar._pill.winfo_x() == bar._buttons["minggu_4"].winfo_x()
    finally:
        tk_root.withdraw()
        bar.destroy()


def test_lebar_pil_menyesuaikan_tombol_yang_lebarnya_beda(tk_root):
    """Segmented button Rekap Dinas lebarnya 53/53/85 — pil harus ikut
    melebar, bukan memakai lebar tetap."""
    motion.set_enabled(False)
    host = ctk.CTkFrame(tk_root)
    host.pack()
    pill = tk.Frame(host, bg=COLOR_ACCENT)
    a = ctk.CTkButton(host, text="3 bln", width=53)
    b = ctk.CTkButton(host, text="Tahun ini", width=85)
    a.place(x=0, y=0)
    b.place(x=53, y=0)
    tk_root.deiconify()
    tk_root.update()
    try:
        motion.slide_pill(pill, b)
        tk_root.update()
        assert pill.winfo_width() == b.winfo_width()
        assert pill.winfo_x() == b.winfo_x()
    finally:
        tk_root.withdraw()
        host.destroy()


def test_keadaan_akhir_warna_identik_dengan_v24(tk_root):
    """Pil-nya tambahan; warna tombol aktif/tak-aktif tidak boleh bergeser."""
    motion.set_enabled(False)
    bar = _bar(tk_root)
    try:
        bar.set_active("minggu_2")
        assert bar._buttons["minggu_2"].cget("text_color") == COLOR_BG
        bar.set_active("semua")
        assert bar._buttons["minggu_2"].cget("fg_color") == "transparent"
    finally:
        bar.destroy()
