from src import config


def test_version_is_v24_0_2():
    assert config.APP_VERSION == "24.0.2"
    assert config.APP_BUILD_DATE == "2026-08-04"


def test_changelog_top_is_v24_0_2():
    top = config.APP_CHANGELOG[0]
    assert top["version"] == "24.0.2"
    assert top["date"] == "2026-08-04"
    assert {k for k, _ in top["changes"]} == {"fix"}
    blob = " ".join(d for _, d in top["changes"]).lower()
    assert "dashboard" in blob
    assert "ranking" in blob
