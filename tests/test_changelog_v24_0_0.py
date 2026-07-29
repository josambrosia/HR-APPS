from src import config


def test_version_is_v24_0_0():
    assert config.APP_VERSION == "24.0.0"
    assert config.APP_BUILD_DATE == "2026-07-30"


def test_changelog_top_is_v24_0_0():
    top = config.APP_CHANGELOG[0]
    assert top["version"] == "24.0.0"
    assert top["date"] == "2026-07-30"
    kinds = {k for k, _ in top["changes"]}
    assert "feat" in kinds
    blob = " ".join(d for _, d in top["changes"]).lower()
    assert "alasan" in blob
    assert "rekap" in blob
    assert "dinas" in blob
    assert "paparan" in blob
