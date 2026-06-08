"""Tests for src.ui.app sidebar — About trigger."""


def test_app_sidebar_has_about_handler():
    """The HRApp class exposes a _show_about method that opens AboutDialog."""
    from src.ui.app import HRApp
    assert hasattr(HRApp, "_show_about"), \
        "HRApp must expose _show_about to wire the About sidebar item"


def test_show_about_imports_and_constructs_dialog(monkeypatch):
    """Calling _show_about constructs an AboutDialog with self as parent."""
    from src.ui.app import HRApp
    import src.ui.dialogs.about_dialog as about_mod
    constructed = []
    monkeypatch.setattr(about_mod, "AboutDialog",
                        lambda parent: constructed.append(parent))
    stub = object()
    HRApp._show_about(stub)
    assert constructed == [stub]
