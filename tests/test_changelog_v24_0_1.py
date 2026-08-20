from src import config


def test_changelog_retains_v24_0_1_entry():
    """v24.0.1 bukan lagi versi terkini, tapi entri changelog-nya harus tetap
    ada (dialog About menampilkan riwayat penuh)."""
    entry = next((e for e in config.APP_CHANGELOG if e["version"] == "24.0.1"), None)
    assert entry is not None
    assert entry["date"] == "2026-08-03"
    blob = " ".join(d for _, d in entry["changes"]).lower()
    assert "rekap dinas paparan" in blob
    assert "tiga panel" in blob
    assert "kecualikan" in blob


def test_menu_renamed_in_sidebar():
    import inspect
    import src.ui.app as app_mod
    src = inspect.getsource(app_mod.HRApp._build_sidebar)
    assert '"Rekap Dinas Paparan", "DinasRecap"' in src
