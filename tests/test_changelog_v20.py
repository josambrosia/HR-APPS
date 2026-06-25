from src import config


def test_changelog_retains_v20_entry():
    """v20.0.0 entry must remain in the changelog history (newer versions prepend,
    they don't drop older entries)."""
    entry = next(
        (e for e in config.APP_CHANGELOG if e["version"] == "20.0.0"), None)
    assert entry is not None, "v20.0.0 changelog entry must be preserved"
    blob = " ".join(d for _, d in entry["changes"])
    assert "Space Grotesk" in blob
    assert "Heatmap" in blob or "heat" in blob
