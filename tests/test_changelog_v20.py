from src import config


def test_version_is_v20():
    assert config.APP_VERSION == "20.0.0"


def test_build_date_is_v20():
    assert config.APP_BUILD_DATE == "2026-06-26"


def test_changelog_top_is_v20():
    top = config.APP_CHANGELOG[0]
    assert top["version"] == "20.0.0"
    assert top["date"] == "2026-06-26"
    kinds = [k for k, _ in top["changes"]]
    assert "feat" in kinds and "change" in kinds
    # design-refresh themes documented in user-facing terms
    blob = " ".join(d for _, d in top["changes"])
    assert "Heatmap" in blob or "heat" in blob
    assert "Space Grotesk" in blob
