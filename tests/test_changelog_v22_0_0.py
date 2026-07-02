from src import config


def test_version_is_v22_0_0():
    assert config.APP_VERSION == "22.0.0"


def test_build_date_is_v22_0_0():
    assert config.APP_BUILD_DATE == "2026-07-03"


def test_changelog_top_is_v22_0_0():
    top = config.APP_CHANGELOG[0]
    assert top["version"] == "22.0.0"
    assert top["date"] == "2026-07-03"
    kinds = [k for k, _ in top["changes"]]
    # v22.0.0 = frontend quality pass (no new features, all behavior polish)
    assert "change" in kinds
    blob = " ".join(d for _, d in top["changes"]).lower()
    assert "latar belakang" in blob      # heavy work off the UI thread
    assert "klik ganda" in blob          # double-click guard
    assert "instan" in blob              # cached navigation
    assert "dialog gelap" in blob        # messagebox replacement
