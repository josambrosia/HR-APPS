from src import config


def test_changelog_retains_v18_heatmap():
    """v18 entry must remain in the changelog history — newer versions
    prepend their entry, they don't drop older ones."""
    entry = next(
        (e for e in config.APP_CHANGELOG if e["version"] == "18.0.0"), None)
    assert entry is not None, "v18.0.0 changelog entry must be preserved"
    kinds = [k for k, _ in entry["changes"]]
    assert "feat" in kinds
    assert any("Heatmap" in d for _, d in entry["changes"])
