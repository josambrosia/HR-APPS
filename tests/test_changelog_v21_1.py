from src import config


def test_changelog_retains_v21_0_1_entry():
    """v21.0.1 entry must remain in history (newer versions prepend, not drop)."""
    entry = next(
        (e for e in config.APP_CHANGELOG if e["version"] == "21.0.1"), None)
    assert entry is not None, "v21.0.1 changelog entry must be preserved"
    blob = " ".join(d for _, d in entry["changes"])
    assert "Report Kehadiran" in blob
    assert "Cetak" in blob
