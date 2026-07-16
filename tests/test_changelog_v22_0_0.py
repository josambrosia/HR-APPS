from src import config


def test_changelog_retains_v22_0_0_entry():
    """v22.0.0 is no longer current, but its changelog entry must survive
    (About dialog shows the full history)."""
    entry = next((e for e in config.APP_CHANGELOG if e["version"] == "22.0.0"), None)
    assert entry is not None
    assert entry["date"] == "2026-07-03"
    kinds = [k for k, _ in entry["changes"]]
    assert "change" in kinds
    blob = " ".join(d for _, d in entry["changes"]).lower()
    assert "latar belakang" in blob      # heavy work off the UI thread
    assert "klik ganda" in blob          # double-click guard
    assert "instan" in blob              # cached navigation
    assert "dialog gelap" in blob        # messagebox replacement
