"""Item 11 & 18 — indikator sibuk yang membuktikan proses masih hidup."""
import customtkinter as ctk

from src.ui import motion
from src.ui.tasks import BusyGuard


def test_teks_sibuk_dipasang_saat_acquire(tk_root):
    motion.set_enabled(False)
    btn = ctk.CTkButton(tk_root, text="Export")
    guard = BusyGuard(btn, busy_text="Memproses")
    try:
        assert guard.acquire() is True
        assert "Memproses" in btn.cget("text")
    finally:
        guard.release()
        btn.destroy()


def test_release_mengembalikan_teks_asli(tk_root):
    motion.set_enabled(False)
    btn = ctk.CTkButton(tk_root, text="Export Laporan")
    guard = BusyGuard(btn, busy_text="Memproses")
    try:
        guard.acquire()
        guard.release()
        assert btn.cget("text") == "Export Laporan"
    finally:
        btn.destroy()


def test_denyut_berhenti_setelah_release(tk_root):
    """Regresi kebocoran: timer denyut harus mati bersama release, kalau
    tidak ia akan terus menulis ke tombol yang sudah kembali normal."""
    motion.set_enabled(True)
    try:
        btn = ctk.CTkButton(tk_root, text="Export")
        guard = BusyGuard(btn, busy_text="Memproses")
        guard.acquire()
        tk_root.update()
        guard.release()
        after = btn.cget("text")
        for _ in range(6):
            tk_root.update()
        assert btn.cget("text") == after, "denyut masih menulis setelah release"
        btn.destroy()
    finally:
        motion.set_enabled(False)


def test_denyut_benar_benar_bergerak_saat_motion_menyala(tk_root):
    """Tes di atas berjalan dengan motion MATI atau tidak menunggu cukup lama
    untuk melihat isi denyutnya — hanya membuktikan ia berhenti, bukan bahwa
    ia pernah benar-benar bergerak. Yang ini menunggu waktu nyata sampai
    teks tombol berubah setidaknya sekali (titik bergerak), lalu memastikan
    itu berhenti lagi setelah release()."""
    import time
    motion.set_enabled(True)
    try:
        btn = ctk.CTkButton(tk_root, text="Export")
        btn.pack()
        guard = BusyGuard(btn, busy_text="Memproses")
        guard.acquire()
        first_text = btn.cget("text")

        seen_change = False
        t0 = time.perf_counter()
        while time.perf_counter() - t0 < 3.0:
            tk_root.update()
            if btn.cget("text") != first_text:
                seen_change = True
                break
        assert seen_change, "teks denyut tidak pernah berubah — animasi tidak jalan"

        guard.release()
        settled = btn.cget("text")
        assert settled == "Export"
        for _ in range(6):
            tk_root.update()
        assert btn.cget("text") == settled, "denyut masih menulis setelah release"
        btn.destroy()
    finally:
        motion.set_enabled(False)


def test_settings_backup_memakai_busy_guard(tk_root):
    """Item 18: settings.py sebelumnya tidak punya run_bg, BusyGuard,
    maupun ProgressModal sama sekali."""
    import inspect
    import src.ui.screens.settings as mod
    source = inspect.getsource(mod)
    assert "BusyGuard" in source, "backup/restore masih tanpa indikator apa pun"
