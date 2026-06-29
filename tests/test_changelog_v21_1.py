from src import config


def test_version_is_v21_1():
    assert config.APP_VERSION == "21.0.1"


def test_build_date_is_v21_1():
    assert config.APP_BUILD_DATE == "2026-06-30"


def test_changelog_top_is_v21_1():
    top = config.APP_CHANGELOG[0]
    assert top["version"] == "21.0.1"
    assert top["date"] == "2026-06-30"
    kinds = [k for k, _ in top["changes"]]
    # v21.0.1 = in-app Cetak-overlap fix + per-employee report redesign
    assert "fix" in kinds and "change" in kinds
    blob = " ".join(d for _, d in top["changes"])
    assert "Report Kehadiran" in blob
    assert "Cetak" in blob
