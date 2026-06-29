from src import config


def test_changelog_retains_v21_entry():
    """v21.0.0 entry must remain in the changelog history (newer versions
    prepend, they don't drop older entries)."""
    entry = next(
        (e for e in config.APP_CHANGELOG if e["version"] == "21.0.0"), None)
    assert entry is not None, "v21.0.0 changelog entry must be preserved"
    blob = " ".join(d for _, d in entry["changes"])
    assert "Terlambat dengan alasan" in blob
