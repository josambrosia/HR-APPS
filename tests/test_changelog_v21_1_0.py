from src import config


def test_version_is_v21_1_0():
    assert config.APP_VERSION == "21.1.0"


def test_build_date_is_v21_1_0():
    assert config.APP_BUILD_DATE == "2026-06-30"


def test_changelog_top_is_v21_1_0():
    top = config.APP_CHANGELOG[0]
    assert top["version"] == "21.1.0"
    assert top["date"] == "2026-06-30"
    kinds = [k for k, _ in top["changes"]]
    # v21.1.0 = heatmap lateness lane + Cetak hover + report on-screen frame
    assert "feat" in kinds and "change" in kinds and "fix" in kinds
    blob = " ".join(d for _, d in top["changes"])
    assert "Pola Keterlambatan" in blob          # the new lateness lane
    assert "hover" in blob                        # Cetak hover affordance
    assert "A4" in blob                           # report on-screen sheet frame
