from src import config


def test_changelog_retains_v24_0_0_entry():
    """v24.0.0 bukan lagi versi terkini, tapi entri changelog-nya harus tetap
    ada (dialog About menampilkan riwayat penuh)."""
    entry = next((e for e in config.APP_CHANGELOG if e["version"] == "24.0.0"), None)
    assert entry is not None
    assert entry["date"] == "2026-07-30"
    kinds = {k for k, _ in entry["changes"]}
    assert "feat" in kinds
    blob = " ".join(d for _, d in entry["changes"]).lower()
    assert "alasan" in blob
    assert "rekap" in blob
    assert "dinas" in blob
    assert "paparan" in blob
