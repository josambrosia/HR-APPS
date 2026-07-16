from src import config


def test_version_is_v23_0_0():
    assert config.APP_VERSION == "23.0.0"
    assert config.APP_BUILD_DATE == "2026-07-16"


def test_changelog_top_is_v23_0_0():
    top = config.APP_CHANGELOG[0]
    assert top["version"] == "23.0.0"
    assert top["date"] == "2026-07-16"
    kinds = {k for k, _ in top["changes"]}
    assert "feat" in kinds
    blob = " ".join(d for _, d in top["changes"]).lower()
    assert "edit data" in blob
    assert "backup" in blob
    assert "konflik" in blob or "konfirmasi" in blob
