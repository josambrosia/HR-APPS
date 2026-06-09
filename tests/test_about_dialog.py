"""Tests for src.ui.dialogs.about_dialog — branded About modal."""
import sys


def _all_text(widget):
    """Recursively gather every text fragment in the widget tree."""
    out = []
    try:
        text = widget.cget("text")
        if text:
            out.append(str(text))
    except Exception:
        pass
    for child in widget.winfo_children():
        out.extend(_all_text(child))
    return out


def test_about_dialog_constructs(tk_root):
    from src.ui.dialogs.about_dialog import AboutDialog
    dlg = AboutDialog(tk_root)
    tk_root.update_idletasks()
    assert dlg is not None
    dlg.destroy()


def test_about_dialog_renders_version_and_build(tk_root):
    from src.ui.dialogs.about_dialog import AboutDialog
    from src.config import APP_VERSION, APP_BUILD_DATE
    dlg = AboutDialog(tk_root)
    tk_root.update_idletasks()
    texts = " ".join(_all_text(dlg))
    assert APP_VERSION in texts
    assert APP_BUILD_DATE in texts
    dlg.destroy()


def test_about_dialog_renders_python_version(tk_root):
    from src.ui.dialogs.about_dialog import AboutDialog
    dlg = AboutDialog(tk_root)
    tk_root.update_idletasks()
    texts = " ".join(_all_text(dlg))
    expected = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    assert expected in texts
    dlg.destroy()


def test_about_dialog_renders_db_path(tk_root):
    from src.ui.dialogs.about_dialog import AboutDialog
    from src.config import DB_PATH
    dlg = AboutDialog(tk_root)
    tk_root.update_idletasks()
    texts = " ".join(_all_text(dlg))
    assert "hr.db" in texts
    dlg.destroy()


def test_about_dialog_binds_esc(tk_root):
    from src.ui.dialogs.about_dialog import AboutDialog
    dlg = AboutDialog(tk_root)
    tk_root.update_idletasks()
    assert dlg.bind("<Escape>") != ""
    dlg.destroy()


def test_about_dialog_renders_changelog_heading(tk_root):
    from src.ui.dialogs.about_dialog import AboutDialog
    dlg = AboutDialog(tk_root)
    tk_root.update_idletasks()
    texts = " ".join(_all_text(dlg))
    assert "Apa yang baru?" in texts
    dlg.destroy()


def test_about_dialog_renders_current_version_entry(tk_root):
    """The first changelog entry (current version) must render its
    first change description."""
    from src.ui.dialogs.about_dialog import AboutDialog
    from src.config import APP_CHANGELOG
    dlg = AboutDialog(tk_root)
    tk_root.update_idletasks()
    texts = " ".join(_all_text(dlg))
    first_change = APP_CHANGELOG[0]["changes"][0][1]
    # Substring of first change description should appear
    # (use first 20 chars to avoid line-wrap issues)
    assert first_change[:20] in texts
    dlg.destroy()
