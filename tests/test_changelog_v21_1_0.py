from src import config


def test_changelog_retains_v21_1_0_entry():
    """v21.1.0 entry must remain in history (newer versions prepend, not drop)."""
    entry = next(
        (e for e in config.APP_CHANGELOG if e["version"] == "21.1.0"), None)
    assert entry is not None, "v21.1.0 changelog entry must be preserved"
    blob = " ".join(d for _, d in entry["changes"])
    assert "Pola Keterlambatan" in blob          # the heatmap lateness lane
