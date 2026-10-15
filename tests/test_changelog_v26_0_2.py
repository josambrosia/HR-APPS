from src import config


def test_versi_naik_ke_26_0_2():
    assert config.APP_VERSION == "26.0.2"


def test_changelog_punya_entri_v26_0_2_paling_atas():
    entry = config.APP_CHANGELOG[0]
    assert entry["version"] == "26.0.2"
    assert entry["date"] == "2026-10-15"
    blob = " ".join(d for _, d in entry["changes"]).lower()
    assert "telat" in blob
    assert "jadwal" in blob
    assert "lembur" in blob


def test_entri_v26_0_1_dan_lama_tetap_ada():
    versions = [e["version"] for e in config.APP_CHANGELOG]
    for v in ("26.0.1", "26.0.0", "25.0.0", "24.0.2"):
        assert v in versions
