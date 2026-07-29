from src import config


def test_changelog_retains_v23_0_0_entry():
    """v23.0.0 bukan lagi versi terkini, tapi entri changelog-nya harus tetap
    ada (dialog About menampilkan riwayat penuh)."""
    entry = next((e for e in config.APP_CHANGELOG if e["version"] == "23.0.0"), None)
    assert entry is not None
    assert entry["date"] == "2026-07-16"
    kinds = {k for k, _ in entry["changes"]}
    assert "feat" in kinds
    blob = " ".join(d for _, d in entry["changes"]).lower()
    assert "edit data" in blob
    assert "backup" in blob
    assert "konflik" in blob or "konfirmasi" in blob
