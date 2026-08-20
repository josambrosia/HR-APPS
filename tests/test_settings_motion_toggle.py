"""Sakelar animasi — jaring pengaman untuk laptop yang belum pernah diukur."""
import pytest

from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.settings import get_setting


@pytest.fixture
def dbp(tmp_path):
    p = tmp_path / "hr.db"
    init_db(p)
    return p


@pytest.fixture(autouse=True)
def _restore_motion_enabled():
    """motion._enabled adalah state global proses — kembalikan ke default
    supaya tes ini tidak membocorkan keadaan ke tes lain."""
    from src.ui import motion
    yield
    motion.set_enabled(True)


def test_mematikan_menulis_setting_dan_berlaku_seketika(tk_root, monkeypatch, dbp):
    from src.ui import motion
    from src.ui.screens import settings as M
    monkeypatch.setattr(M, "DB_PATH", dbp)
    s = M.SettingsScreen(tk_root)
    try:
        s._on_motion_toggle(False)
        with get_connection(dbp) as conn:
            assert get_setting(conn, "motion_enabled") == "0"
        assert motion.enabled() is False
    finally:
        s.destroy()


def test_menyalakan_kembali_menulis_satu(tk_root, monkeypatch, dbp):
    from src.ui import motion
    from src.ui.screens import settings as M
    monkeypatch.setattr(M, "DB_PATH", dbp)
    s = M.SettingsScreen(tk_root)
    try:
        s._on_motion_toggle(False)
        s._on_motion_toggle(True)
        with get_connection(dbp) as conn:
            assert get_setting(conn, "motion_enabled") == "1"
        assert motion.enabled() is True
    finally:
        s.destroy()


def test_mematikan_menghentikan_tween_tidak_ada_timer_dijadwalkan(tk_root, monkeypatch, dbp):
    """Bukti perilaku, bukan cuma setting: setelah sakelar dimatikan, tween
    berjalan seketika (on_frame(1.0) langsung) tanpa menjadwalkan timer apa
    pun — active_count() harus tetap nol sepanjang panggilan."""
    from src.ui import motion
    from src.ui.screens import settings as M
    monkeypatch.setattr(M, "DB_PATH", dbp)
    s = M.SettingsScreen(tk_root)
    try:
        s._on_motion_toggle(False)

        import customtkinter as ctk
        probe = ctk.CTkLabel(tk_root, text="0")

        frames = []
        try:
            job = motion.tween(probe, 300, lambda t: frames.append(t))
            assert job is None
            assert frames == [1.0]
            assert motion.active_count() == 0
        finally:
            probe.destroy()
    finally:
        s.destroy()
