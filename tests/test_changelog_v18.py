from src import config


def test_version_is_v18():
    assert config.APP_VERSION == "18.0.0"


def test_changelog_top_is_v18_heatmap():
    top = config.APP_CHANGELOG[0]
    assert top["version"] == "18.0.0"
    kinds = [k for k, _ in top["changes"]]
    assert "feat" in kinds
    assert any("Heatmap" in d for _, d in top["changes"])
