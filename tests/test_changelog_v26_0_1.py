from src import config


def test_changelog_retains_v26_0_1_entry():
    """v26.0.1 bukan lagi versi terkini, tapi entri changelog-nya tetap ada."""
    entry = next((e for e in config.APP_CHANGELOG if e["version"] == "26.0.1"),
                 None)
    assert entry is not None
    assert entry["date"] == "2026-10-15"
    blob = " ".join(d for _, d in entry["changes"]).lower()
    assert "diagnostik" in blob
    assert "backup" in blob


def test_entri_v26_0_0_dan_lama_tetap_ada():
    versions = [e["version"] for e in config.APP_CHANGELOG]
    for v in ("26.0.0", "25.0.0", "24.0.2"):
        assert v in versions
