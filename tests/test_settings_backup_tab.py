"""Smoke: the Backup & Restore tab builds and renders without error.

Uses a real temp DB (init_db) monkeypatched into the settings module so the
General tab's settings reads work, and an empty backups dir so _render_backups
hits the empty-state path. Uses the session-wide `tk_root` fixture from
conftest — Windows/Tkinter cannot create a fresh Tk() once an earlier root was
destroyed, so per-test roots collide and make tests skip at random.
"""


def test_backup_tab_builds(tmp_path, monkeypatch, tk_root):
    from src.ui.screens import settings as S
    from src.db.schema import init_db

    dbp = tmp_path / "hr.db"
    init_db(dbp)
    monkeypatch.setattr(S, "DB_PATH", dbp)

    scr = S.SettingsScreen(tk_root)
    try:
        # empty dir -> "(belum ada backup)" path
        scr._render_backups()
        # create one snapshot, re-render -> row path
        from src.db import backup
        backup.create_backup(dbp, reason="manual")
        scr._render_backups()
    finally:
        scr.destroy()
