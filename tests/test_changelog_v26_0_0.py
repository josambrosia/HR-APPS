from src import config


def test_versi_naik_ke_26():
    assert config.APP_VERSION == "26.0.0"


def test_changelog_punya_entri_v26_paling_atas():
    entry = config.APP_CHANGELOG[0]
    assert entry["version"] == "26.0.0"
    assert entry["date"] == "2026-10-01"
    blob = " ".join(d for _, d in entry["changes"]).lower()
    assert "lembur" in blob
    assert "jam kantor" in blob


def test_changelog_v26_menyebut_status_verifikasi():
    entry = config.APP_CHANGELOG[0]
    blob = " ".join(d for _, d in entry["changes"]).lower()
    assert "open" in blob and "diajukan" in blob and "diterima" in blob


def test_entri_lama_tetap_ada():
    versions = [e["version"] for e in config.APP_CHANGELOG]
    for v in ("25.0.0", "24.0.2", "24.0.1", "24.0.0"):
        assert v in versions
