from src import config


def test_version_is_v24_0_1():
    assert config.APP_VERSION == "24.0.1"
    assert config.APP_BUILD_DATE == "2026-08-03"


def test_changelog_top_is_v24_0_1():
    top = config.APP_CHANGELOG[0]
    assert top["version"] == "24.0.1"
    assert top["date"] == "2026-08-03"
    blob = " ".join(d for _, d in top["changes"]).lower()
    assert "rekap dinas paparan" in blob
    assert "tiga panel" in blob
    assert "kecualikan" in blob
    assert "urutkan" in blob or "diurutkan" in blob


def test_menu_renamed_in_sidebar():
    import inspect
    import src.ui.app as app_mod
    src = inspect.getsource(app_mod.HRApp._build_sidebar)
    assert '"Rekap Dinas Paparan", "DinasRecap"' in src
