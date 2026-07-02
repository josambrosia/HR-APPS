from src import config


def test_changelog_retains_v21_2_0_entry():
    """v21.2.0 entry must remain in history (newer versions prepend, not drop)."""
    entry = next(
        (e for e in config.APP_CHANGELOG if e["version"] == "21.2.0"), None)
    assert entry is not None, "v21.2.0 changelog entry must be preserved"
    assert entry["date"] == "2026-07-02"
    kinds = [k for k, _ in entry["changes"]]
    # v21.2.0 = WhatsApp Assistant compose redesign
    assert "feat" in kinds and "change" in kinds
    blob = " ".join(d for _, d in entry["changes"]).lower()
    assert "preview" in blob                       # live WhatsApp preview
    assert "sudah terisi" in blob                  # prefilled wa.me text
    assert "sudah dihubungi" in blob               # contact tracking
