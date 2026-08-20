"""Item 03 — angka KPI berhitung naik, dan hanya saat datanya berubah."""
import customtkinter as ctk

from src.ui import motion


def test_count_up_mendarat_tepat_di_nilai_akhir(tk_root):
    motion.set_enabled(False)
    lbl = ctk.CTkLabel(tk_root, text="0")
    motion.count_up(lbl, 4238)
    assert lbl.cget("text") == "4238"
    lbl.destroy()


def test_count_up_menghormati_formatter(tk_root):
    motion.set_enabled(False)
    lbl = ctk.CTkLabel(tk_root, text="")
    motion.count_up(lbl, 87, fmt=lambda v: f"{v} mnt")
    assert lbl.cget("text") == "87 mnt"
    lbl.destroy()


def test_count_up_nilai_nol_tetap_menulis_nol(tk_root):
    motion.set_enabled(False)
    lbl = ctk.CTkLabel(tk_root, text="99")
    motion.count_up(lbl, 0)
    assert lbl.cget("text") == "0"
    lbl.destroy()


def test_dashboard_tidak_menganimasikan_kunjungan_ulang_tanpa_perubahan(tk_root, monkeypatch, tmp_path):
    """Regresi jebakan #2: layar disimpan di cache sejak v22, jadi tanpa
    RenderSignature animasi masuk akan main ulang tiap bolak-balik menu."""
    from src.db.schema import init_db
    from src.db.connection import get_connection
    from src.db.settings import set_setting
    from src.ui.screens import dashboard as M

    p = tmp_path / "hr.db"
    init_db(p)
    with get_connection(p) as conn:
        set_setting(conn, "current_month", "2026-07")
    monkeypatch.setattr(M, "DB_PATH", p)

    s = M.DashboardScreen(tk_root)
    try:
        assert s._anim_sig.changed(*s._anim_parts()) is False, \
            "render pertama sudah mencatat sidik jarinya"
        s.on_show()
        assert s._anim_sig.changed(*s._anim_parts()) is False, \
            "kunjungan ulang tanpa perubahan data seharusnya tidak menganimasikan"
    finally:
        s.destroy()
