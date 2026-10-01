from src import config


def test_changelog_retains_v25_entry():
    """v25.0.0 bukan lagi versi terkini, tapi entri changelog-nya harus tetap
    ada (dialog About menampilkan riwayat penuh)."""
    entry = next((e for e in config.APP_CHANGELOG if e["version"] == "25.0.0"), None)
    assert entry is not None
    assert entry["date"] == "2026-08-21"
    kinds = {k for k, _ in entry["changes"]}
    assert "fix" in kinds, "4 dari 17 item menutup cacat — harus tercermin"
    assert "feat" in kinds
    blob = " ".join(d for _, d in entry["changes"]).lower()
    assert "animasi" in blob


def test_entri_lama_tetap_ada():
    versions = [e["version"] for e in config.APP_CHANGELOG]
    for v in ("24.0.2", "24.0.1", "24.0.0"):
        assert v in versions
