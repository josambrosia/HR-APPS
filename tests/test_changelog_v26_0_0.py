from src import config


def test_changelog_retains_v26_0_0_entry():
    """v26.0.0 bukan lagi versi terkini, tapi entri changelog-nya tetap ada."""
    entry = next((e for e in config.APP_CHANGELOG if e["version"] == "26.0.0"),
                 None)
    assert entry is not None
    assert entry["date"] == "2026-10-01"
    blob = " ".join(d for _, d in entry["changes"]).lower()
    assert "lembur" in blob
    assert "jam kantor" in blob
    kinds = {k for k, _ in entry["changes"]}
    assert "fix" in kinds
    assert "sidebar" in blob


def test_entri_lama_tetap_ada():
    versions = [e["version"] for e in config.APP_CHANGELOG]
    for v in ("25.0.0", "24.0.2", "24.0.1", "24.0.0"):
        assert v in versions
