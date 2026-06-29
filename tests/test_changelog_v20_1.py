from src import config


def test_changelog_retains_v20_1_entry():
    """v20.0.1 entry must remain in the changelog history (newer versions
    prepend, they don't drop older entries)."""
    entry = next(
        (e for e in config.APP_CHANGELOG if e["version"] == "20.0.1"), None)
    assert entry is not None, "v20.0.1 changelog entry must be preserved"
    blob = " ".join(d for _, d in entry["changes"])
    assert "Headers and footers" in blob
