from src import config


def test_changelog_retains_v19_entry():
    """v19 entry must remain in the changelog history (newer versions prepend,
    they don't drop older entries)."""
    entry = next(
        (e for e in config.APP_CHANGELOG if e["version"] == "19.0.0"), None)
    assert entry is not None, "v19.0.0 changelog entry must be preserved"
    assert any("Detail" in d for _, d in entry["changes"])
    assert any("Dashboard" in d for _, d in entry["changes"])
