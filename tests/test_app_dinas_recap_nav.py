"""Item nav 'Rekap Dinas' terdaftar dan membuat layar yang benar."""


def test_nav_item_registered_in_insight_group():
    import inspect
    import src.ui.app as app_mod
    src = inspect.getsource(app_mod.HRApp._build_sidebar)
    assert '"Rekap Dinas", "DinasRecap"' in src
    # harus berada di grup INSIGHT (muncul sebelum label DATA MANAGEMENT)
    assert src.index("Rekap Dinas") < src.index("DATA MANAGEMENT")


def test_create_screen_returns_dinas_recap(tk_root, monkeypatch, tmp_path):
    from src.db.schema import init_db
    from src.db.connection import get_connection
    from src.db.settings import set_setting
    import src.ui.screens.dinas_recap as screen_mod
    from src.ui.screens.dinas_recap import DinasRecapScreen

    p = tmp_path / "hr.db"
    init_db(p)
    with get_connection(p) as conn:
        set_setting(conn, "current_month", "2026-07")
    monkeypatch.setattr(screen_mod, "DB_PATH", p)

    import src.ui.app as app_mod
    dummy = type("D", (), {"content": tk_root})()
    screen = app_mod.HRApp._create_screen(dummy, "DinasRecap")
    try:
        assert isinstance(screen, DinasRecapScreen)
    finally:
        screen.destroy()
