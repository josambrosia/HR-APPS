# tests/test_changelog_v17.py
from src import config


def test_v17_entry_retained():
    """After a newer release supersedes v17, its changelog entry must still be
    present (history is never dropped) — it is just no longer the top entry.
    The current-version assertion lives in the newest version's changelog test."""
    versions = [e["version"] for e in config.APP_CHANGELOG]
    assert "17.0.0" in versions
    entry = next(e for e in config.APP_CHANGELOG if e["version"] == "17.0.0")
    kinds = [k for k, _ in entry["changes"]]
    assert "feat" in kinds
    assert any("Severe Lateness" in desc for _, desc in entry["changes"])
