# tests/test_browser_launcher_url.py
import src.ui.browser_launcher as bl


def test_open_url_passes_url_not_path(monkeypatch):
    captured = {}
    monkeypatch.setattr(bl.shutil, "which", lambda exe: r"C:\fake\chrome.exe")
    monkeypatch.setattr(bl.subprocess, "Popen", lambda args: captured.setdefault("args", args))
    monkeypatch.setattr(bl.sys, "platform", "win32")
    ok, name = bl.open_html_in_browser("http://127.0.0.1:8765/heatmap?month=2026-05")
    assert ok
    assert captured["args"][1] == "http://127.0.0.1:8765/heatmap?month=2026-05"
