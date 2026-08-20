from src import config


def test_versi_naik_ke_25():
    assert config.APP_VERSION == "25.0.0"


def test_changelog_punya_entri_v25_paling_atas():
    entry = config.APP_CHANGELOG[0]
    assert entry["version"] == "25.0.0"
    assert entry["date"] == "2026-08-21"
    blob = " ".join(d for _, d in entry["changes"]).lower()
    assert "animasi" in blob


def test_changelog_menyebut_perbaikan_bukan_hanya_hiasan():
    entry = config.APP_CHANGELOG[0]
    kinds = {k for k, _ in entry["changes"]}
    assert "fix" in kinds, "4 dari 17 item menutup cacat — harus tercermin"
    assert "feat" in kinds


def test_entri_lama_tetap_ada():
    versions = [e["version"] for e in config.APP_CHANGELOG]
    for v in ("24.0.2", "24.0.1", "24.0.0"):
        assert v in versions
