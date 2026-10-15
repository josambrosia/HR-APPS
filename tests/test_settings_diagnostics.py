"""v26.0.1: tombol Ekspor Diagnostik di Settings → Backup & Restore."""
import zipfile

import pytest

from src.db.schema import init_db


@pytest.fixture
def env(tmp_path, monkeypatch):
    import src.ui.screens.settings as settings_mod
    dbp = tmp_path / "hr.db"
    init_db(dbp)
    monkeypatch.setattr(settings_mod, "DB_PATH", dbp)
    monkeypatch.setattr(settings_mod.feedback, "show_info",
                        lambda *a, **k: None)
    monkeypatch.setattr(settings_mod.feedback, "show_error",
                        lambda *a, **k: None)
    return settings_mod, dbp


def test_export_diagnostics_creates_zip(env, tk_root, tmp_path, monkeypatch):
    settings_mod, dbp = env
    out = tmp_path / "diag"
    out.mkdir()
    monkeypatch.setattr("tkinter.filedialog.askdirectory",
                        lambda **k: str(out))
    s = settings_mod.SettingsScreen(tk_root)
    tk_root.update_idletasks()
    try:
        s._do_export_diagnostics()
        zips = list(out.glob("hr-diagnostik-*.zip"))
        assert len(zips) == 1
        with zipfile.ZipFile(zips[0]) as z:
            assert "hr.db" in z.namelist()
            assert "summary.json" in z.namelist()
    finally:
        s.destroy()


def test_export_diagnostics_cancel_is_noop(env, tk_root, tmp_path,
                                           monkeypatch):
    settings_mod, dbp = env
    monkeypatch.setattr("tkinter.filedialog.askdirectory", lambda **k: "")
    s = settings_mod.SettingsScreen(tk_root)
    tk_root.update_idletasks()
    try:
        s._do_export_diagnostics()   # tidak boleh error / membuat file
        assert list(tmp_path.glob("hr-diagnostik-*.zip")) == []
    finally:
        s.destroy()
