from src import config


def test_version_is_v21_2_0():
    assert config.APP_VERSION == "21.2.0"


def test_build_date_is_v21_2_0():
    assert config.APP_BUILD_DATE == "2026-07-02"


def test_changelog_top_is_v21_2_0():
    top = config.APP_CHANGELOG[0]
    assert top["version"] == "21.2.0"
    assert top["date"] == "2026-07-02"
    kinds = [k for k, _ in top["changes"]]
    # v21.2.0 = WhatsApp Assistant compose redesign
    assert "feat" in kinds and "change" in kinds
    blob = " ".join(d for _, d in top["changes"]).lower()
    assert "preview" in blob                       # live WhatsApp preview
    assert "sudah terisi" in blob                  # prefilled wa.me text
    assert "sudah dihubungi" in blob               # contact tracking
