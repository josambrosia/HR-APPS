# tests/test_browser_launcher_file_path.py
from pathlib import Path

import src.ui.browser_launcher as bl


def test_open_accepts_str_and_path_file(monkeypatch, tmp_path):
    """A plain str filesystem path (e.g. from tempfile.mkstemp) must not crash
    on .as_uri(). Regression: heatmap Cetak passed a str and raised
    AttributeError before the browser ever launched."""
    f = tmp_path / "x.html"
    f.write_text("<html></html>", encoding="utf-8")
    calls = []
    monkeypatch.setattr(bl.shutil, "which",
                        lambda exe: r"C:\fake\chrome.exe" if exe == "chrome.exe" else None)
    monkeypatch.setattr(bl.subprocess, "Popen", lambda args: calls.append(args))
    monkeypatch.setattr(bl.webbrowser, "open", lambda u: calls.append(("web", u)))

    ok_str, _ = bl.open_html_in_browser(str(f))
    ok_path, _ = bl.open_html_in_browser(Path(f))
    assert ok_str is True and ok_path is True
    assert calls  # a browser path was actually invoked (no early crash)
