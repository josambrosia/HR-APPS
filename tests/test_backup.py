from datetime import datetime

from src.db import backup


def _mkdb(tmp_path, content=b"DBDATA"):
    p = tmp_path / "hr.db"
    p.write_bytes(content)
    return p


def test_create_backup_copies_file_with_reason_slug(tmp_path):
    db = _mkdb(tmp_path)
    now = datetime(2026, 7, 16, 14, 20, 5)
    dest = backup.create_backup(db, reason="import", now=now)
    assert dest.name == "hr-20260716-142005-sebelum-import.db"
    assert dest.read_bytes() == b"DBDATA"
    assert dest.parent == tmp_path / "backups"


def test_unknown_reason_falls_back_to_manual(tmp_path):
    db = _mkdb(tmp_path)
    dest = backup.create_backup(db, reason="weird", now=datetime(2026, 7, 16, 1, 2, 3))
    assert dest.name == "hr-20260716-010203-manual.db"


def test_list_backups_newest_first(tmp_path):
    db = _mkdb(tmp_path)
    backup.create_backup(db, reason="manual", now=datetime(2026, 7, 15, 9, 0, 0))
    backup.create_backup(db, reason="import", now=datetime(2026, 7, 16, 9, 0, 0))
    rows = backup.list_backups(db)
    assert [r["reason"] for r in rows] == ["sebelum-import", "manual"]
    assert rows[0]["created_at"] == datetime(2026, 7, 16, 9, 0, 0)
    assert rows[0]["size_bytes"] == len(b"DBDATA")


def test_list_backups_empty_when_no_dir(tmp_path):
    db = _mkdb(tmp_path)
    assert backup.list_backups(db) == []


def test_restore_backs_up_current_then_overwrites(tmp_path):
    db = tmp_path / "hr.db"
    db.write_bytes(b"CURRENT")
    snap = backup.create_backup(db, reason="manual", now=datetime(2026, 7, 1, 8, 0, 0))
    db.write_bytes(b"CHANGED")                      # simulate later edits
    now = datetime(2026, 7, 16, 10, 0, 0)
    pre = backup.restore_backup(db, snap, now=now)
    assert db.read_bytes() == b"CURRENT"            # restored
    assert pre.name == "hr-20260716-100000-sebelum-restore.db"
    assert pre.read_bytes() == b"CHANGED"           # pre-restore safety snapshot
