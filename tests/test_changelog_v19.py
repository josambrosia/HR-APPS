from src import config


def test_version_is_v19():
    assert config.APP_VERSION == "19.0.0"


def test_build_date_is_v19():
    assert config.APP_BUILD_DATE == "2026-06-25"


def test_changelog_top_is_v19():
    top = config.APP_CHANGELOG[0]
    assert top["version"] == "19.0.0"
    assert top["date"] == "2026-06-25"
    kinds = [k for k, _ in top["changes"]]
    assert "fix" in kinds
    # Both bug fixes documented in user-facing terms.
    assert any("Detail" in d for _, d in top["changes"])
    assert any("Dashboard" in d for _, d in top["changes"])
