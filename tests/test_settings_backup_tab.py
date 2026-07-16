"""Smoke: the Backup & Restore tab builds and renders without error.

Uses a real temp DB (init_db) monkeypatched into the settings module so the
General tab's settings reads work, and an empty backups dir so _render_backups
hits the empty-state path. Skips cleanly if no Tk display is available.
"""
import pytest


def test_backup_tab_builds(tmp_path, monkeypatch):
    ctk = pytest.importorskip("customtkinter")
    from src.ui.screens import settings as S
    from src.db.schema import init_db

    dbp = tmp_path / "hr.db"
    init_db(dbp)
    monkeypatch.setattr(S, "DB_PATH", dbp)

    try:
        root = ctk.CTk()
    except Exception as exc:  # pragma: no cover - headless CI
        pytest.skip(f"no Tk display: {exc}")
    root.withdraw()
    try:
        scr = S.SettingsScreen(root)
        # empty dir -> "(belum ada backup)" path
        scr._render_backups()
        # create one snapshot, re-render -> row path
        from src.db import backup
        backup.create_backup(dbp, reason="manual")
        scr._render_backups()
    finally:
        root.destroy()
