"""Force-open HTML in a real browser, not whatever app is associated with .html.

On Windows, .html files are often associated with code editors (VSCode,
Sublime, Notepad++) rather than browsers — especially on developer
machines. The stdlib `webbrowser.open()` uses file associations on
Windows, so it inherits this misrouting.

This helper tries known browser executables explicitly. Preference order:
Chrome → Edge → Brave → Firefox. Edge is fallback because it's always
on Windows 10/11.
"""
import shutil
import subprocess
import sys
import webbrowser
from pathlib import Path
from typing import Tuple

# (Display name, exe name to look up via PATH)
_PATH_CANDIDATES = [
    ("Chrome", "chrome.exe"),
    ("Edge", "msedge.exe"),
    ("Brave", "brave.exe"),
    ("Firefox", "firefox.exe"),
]

# Fallback hard-coded install paths if not in PATH
_INSTALL_PATHS = [
    ("Chrome", r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    ("Chrome", r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    ("Edge", r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    ("Edge", r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    ("Brave", r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"),
    ("Firefox", r"C:\Program Files\Mozilla Firefox\firefox.exe"),
    ("Firefox", r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe"),
]


def open_html_in_browser(html_path: Path) -> Tuple[bool, str]:
    """Open an HTML file in a real browser. Returns (success, browser_name)."""
    if sys.platform != "win32":
        webbrowser.open(html_path.as_uri())
        return True, "default"

    # 1) Try PATH lookup
    for name, exe in _PATH_CANDIDATES:
        located = shutil.which(exe)
        if located:
            subprocess.Popen([located, str(html_path)])
            return True, name

    # 2) Try hard-coded install paths
    for name, path in _INSTALL_PATHS:
        if Path(path).exists():
            subprocess.Popen([path, str(html_path)])
            return True, name

    # 3) Last resort — may open the file-associated app (VSCode etc.)
    webbrowser.open(html_path.as_uri())
    return False, "default app for .html"
