from datetime import datetime, timedelta

from src.db import backup


def _seed(tmp_path, specs):
    """specs: list of (datetime, size_bytes). Writes snapshot files directly."""
    d = tmp_path / "backups"
    d.mkdir(parents=True, exist_ok=True)
    for dt, size in specs:
        (d / f"hr-{dt:%Y%m%d}-{dt:%H%M%S}-manual.db").write_bytes(b"x" * size)
    (tmp_path / "hr.db").write_bytes(b"x")


def test_prune_removes_older_than_one_year_but_keeps_floor(tmp_path):
    now = datetime(2026, 7, 16, 12, 0, 0)
    # 3 recent + 4 very old (>365d). floor=5 protects the 5 newest regardless of age.
    specs = [(now - timedelta(days=k), 10) for k in (1, 2, 3)]
    specs += [(now - timedelta(days=400 + k), 10) for k in range(4)]
    _seed(tmp_path, specs)
    backup.prune_backups(tmp_path / "hr.db", now=now)
    remaining = backup.list_backups(tmp_path / "hr.db")
    # 7 total; floor keeps 5 newest; the 2 unprotected are both >365d -> removed -> 5 left
    assert len(remaining) == 5


def test_prune_enforces_size_budget_oldest_first(tmp_path):
    now = datetime(2026, 7, 16, 12, 0, 0)
    specs = [(now - timedelta(hours=k), 100) for k in range(10)]   # all recent
    _seed(tmp_path, specs)
    backup.prune_backups(tmp_path / "hr.db", now=now,
                         max_total_bytes=650, keep_min=5)
    remaining = backup.list_backups(tmp_path / "hr.db")
    # floor 5 protected (500B); budget 650 allows exactly 1 more survivor (600B) -> 6 files
    assert len(remaining) == 6


def test_prune_never_below_floor_even_if_all_old(tmp_path):
    now = datetime(2026, 7, 16, 12, 0, 0)
    specs = [(now - timedelta(days=500 + k), 10) for k in range(8)]  # all ancient
    _seed(tmp_path, specs)
    backup.prune_backups(tmp_path / "hr.db", now=now, keep_min=5)
    assert len(backup.list_backups(tmp_path / "hr.db")) == 5
