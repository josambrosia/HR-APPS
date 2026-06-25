from src import config


def test_version_is_v20_1():
    assert config.APP_VERSION == "20.0.1"


def test_build_date_is_v20_1():
    assert config.APP_BUILD_DATE == "2026-06-26"


def test_changelog_top_is_v20_1():
    top = config.APP_CHANGELOG[0]
    assert top["version"] == "20.0.1"
    assert top["date"] == "2026-06-26"
    kinds = [k for k, _ in top["changes"]]
    # v20.0.1 is a print-polish patch: bug fixes + small features + a behaviour change
    assert "feat" in kinds and "fix" in kinds and "change" in kinds
    blob = " ".join(d for _, d in top["changes"])
    assert "Heatmap" in blob
    assert "Headers and footers" in blob
