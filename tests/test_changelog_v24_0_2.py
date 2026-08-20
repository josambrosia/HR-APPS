from src import config


def test_changelog_retains_v24_0_2_entry():
    """v24.0.2 bukan lagi versi terkini, tapi entri changelog-nya harus tetap
    ada (dialog About menampilkan riwayat penuh)."""
    entry = next((e for e in config.APP_CHANGELOG if e["version"] == "24.0.2"), None)
    assert entry is not None
    assert entry["date"] == "2026-08-04"
    assert {k for k, _ in entry["changes"]} == {"fix"}
    blob = " ".join(d for _, d in entry["changes"]).lower()
    assert "dashboard" in blob
    assert "ranking" in blob
