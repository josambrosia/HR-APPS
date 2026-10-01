"""Item nav 'Lembur' terdaftar dan membuat layar yang benar."""


def test_nav_item_registered_in_workflow_group():
    import inspect
    import src.ui.app as app_mod
    src = inspect.getsource(app_mod.HRApp._build_sidebar)
    assert '"Lembur", "Overtime"' in src
    # harus di grup WORKFLOW (antara label WORKFLOW dan EXCEPTIONAL CASE)
    assert src.index("WORKFLOW") < src.index('"Lembur", "Overtime"')
    assert src.index('"Lembur", "Overtime"') < src.index("EXCEPTIONAL CASE")


def test_icon_registered():
    from src.ui.icons import GLYPHS
    assert "Overtime" in GLYPHS
    assert len(GLYPHS["Overtime"]) == 1


def test_create_screen_returns_overtime(tk_root, monkeypatch, tmp_path):
    from src.db.schema import init_db
    from src.db.connection import get_connection
    from src.db.settings import set_setting
    import src.ui.screens.overtime as screen_mod
    from src.ui.screens.overtime import OvertimeScreen

    p = tmp_path / "hr.db"
    init_db(p)
    with get_connection(p) as conn:
        set_setting(conn, "current_month", "2026-10")
    monkeypatch.setattr(screen_mod, "DB_PATH", p)

    import src.ui.app as app_mod
    dummy = type("D", (), {"content": tk_root})()
    screen = app_mod.HRApp._create_screen(dummy, "Overtime")
    try:
        assert isinstance(screen, OvertimeScreen)
    finally:
        screen.destroy()
