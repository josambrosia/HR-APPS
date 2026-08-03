"""Overlay 'Memuat…' + pemasangannya di shell navigasi."""
import pytest

from src.ui.components.loading_overlay import LoadingOverlay


@pytest.fixture(autouse=True)
def reset_slow_screens():
    """_slow_screens sengaja global & adaptif — ia belajar dari waktu nyata,
    termasuk dari test lain yang memanggil _show() pada DB kosong (di sana
    layar berat jadi cepat lalu ter-demote). Kembalikan ke bibit tiap test
    agar berkas ini tidak bergantung pada urutan eksekusi."""
    import src.ui.app as app_mod
    saved = set(app_mod._slow_screens)
    app_mod._slow_screens.clear()
    app_mod._slow_screens.update(app_mod._SEED_SLOW)
    yield
    app_mod._slow_screens.clear()
    app_mod._slow_screens.update(saved)


def test_overlay_covers_parent_and_animates(tk_root):
    import customtkinter as ctk
    host = ctk.CTkFrame(tk_root, width=400, height=300)
    host.pack()
    ov = LoadingOverlay(host, text="Memuat Dashboard…", detail="menyiapkan data")
    try:
        ov.show()
        assert ov.winfo_manager() == "place"
        assert ov._job is not None          # animasi terjadwal
        first = ov._angle
        ov._tick()
        assert ov._angle != first           # sudut benar-benar berputar
    finally:
        ov.hide()
        host.destroy()


def test_hide_is_idempotent_and_cancels_animation(tk_root):
    import customtkinter as ctk
    host = ctk.CTkFrame(tk_root)
    host.pack()
    ov = LoadingOverlay(host)
    ov.show()
    ov.hide()
    assert ov._job is None
    ov.hide()                                # tidak boleh melempar
    host.destroy()


def test_set_text_updates_label(tk_root):
    import customtkinter as ctk
    host = ctk.CTkFrame(tk_root)
    host.pack()
    ov = LoadingOverlay(host, text="awal")
    try:
        ov.set_text("berubah")
        assert ov._label.cget("text") == "berubah"
    finally:
        ov.hide()
        host.destroy()


# ---- integrasi dengan shell ----

def test_slow_screens_seeded_from_measurement():
    import src.ui.app as app_mod
    for name in ("Dashboard", "Heatmap", "DinasRecap", "Outlier"):
        assert app_mod._is_slow_screen(name), f"{name} harus memicu overlay"


def test_timing_promotes_and_demotes_screens():
    import src.ui.app as app_mod
    original = set(app_mod._slow_screens)
    try:
        app_mod._record_screen_timing("Settings", app_mod.SLOW_SCREEN_MS + 50)
        assert app_mod._is_slow_screen("Settings")      # naik jadi lambat
        app_mod._record_screen_timing("Settings", 5.0)
        assert not app_mod._is_slow_screen("Settings")  # turun lagi
    finally:
        app_mod._slow_screens.clear()
        app_mod._slow_screens.update(original)


def test_fast_screen_gets_no_overlay(tk_root):
    import customtkinter as ctk
    import src.ui.app as app_mod
    host = ctk.CTkFrame(tk_root)
    host.pack()
    original = set(app_mod._slow_screens)
    try:
        app_mod._slow_screens.discard("Settings")
        assert app_mod._open_loading(host, "Settings", first_visit=True) is None
    finally:
        app_mod._slow_screens.clear()
        app_mod._slow_screens.update(original)
        host.destroy()


def test_slow_screen_gets_overlay_with_screen_label(tk_root):
    import customtkinter as ctk
    import src.ui.app as app_mod
    host = ctk.CTkFrame(tk_root, width=400, height=300)
    host.pack()
    ov = app_mod._open_loading(host, "DinasRecap", first_visit=True)
    try:
        assert ov is not None
        assert "Rekap Dinas" in ov._label.cget("text")
    finally:
        if ov is not None:
            ov.hide()
        host.destroy()


def test_navigation_still_works_and_cleans_up_overlay(tk_root, temp_db_path, monkeypatch):
    """Overlay tidak boleh tertinggal menutupi layar setelah navigasi."""
    import customtkinter as ctk
    from src.db.schema import init_db
    from src.ui.app import HRApp
    import src.ui.screens.dashboard as dash_mod

    init_db(temp_db_path)
    monkeypatch.setattr(dash_mod, "DB_PATH", temp_db_path)

    class Shell:
        _show = HRApp._show
        _create_screen = HRApp._create_screen

        def __init__(self, root):
            self.content = ctk.CTkFrame(root)
            self.content.grid_rowconfigure(0, weight=1)
            self.content.grid_columnconfigure(0, weight=1)
            self._screens = {}
            self._visible_name = ""

        def _refresh_active_month_label(self): pass
        def _set_active_nav_item(self, name): pass
        def _show_about(self): pass

    shell = Shell(tk_root)
    try:
        shell._show("Dashboard")            # layar berbibit lambat
        assert "Dashboard" in shell._screens
        leftover = [w for w in shell.content.place_slaves()
                    if isinstance(w, LoadingOverlay)]
        assert leftover == [], "overlay tertinggal menutupi layar"
    finally:
        shell.content.destroy()
