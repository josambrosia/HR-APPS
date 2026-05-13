"""Tests for module-level helpers in src.ui.screens.import_screen.

These helpers underpin the drag-and-drop crash fix: extracting the path
filter to a pure function (testable without CTk) and the crash logger
(testable without a real .exe / windnd hook).
"""
from pathlib import Path

from src.ui.screens.import_screen import _filter_excel_paths, _log_dnd_crash


def test_filter_excel_paths_keeps_xls_and_xlsx():
    files = [r"C:\data\report.xlsx", r"C:\data\old.xls"]
    result = _filter_excel_paths(files)
    assert len(result) == 2
    assert all(isinstance(p, Path) for p in result)
    assert {p.suffix.lower() for p in result} == {".xls", ".xlsx"}


def test_filter_excel_paths_drops_non_excel():
    files = [r"C:\data\note.txt", r"C:\data\image.png", r"C:\data\doc.pdf"]
    assert _filter_excel_paths(files) == []


def test_filter_excel_paths_handles_bytes_paths():
    """windnd with force_unicode=False delivers bytes; we still must decode."""
    files = [b"C:\\data\\bytes.xlsx", b"C:\\data\\skip.txt"]
    result = _filter_excel_paths(files)
    assert len(result) == 1
    assert result[0].name == "bytes.xlsx"


def test_filter_excel_paths_mixed_bytes_and_str():
    files = [b"C:\\a.xlsx", r"C:\b.xls", b"C:\\c.txt", "C:\\d.png"]
    result = _filter_excel_paths(files)
    assert sorted(p.name for p in result) == ["a.xlsx", "b.xls"]


def test_filter_excel_paths_empty_input():
    assert _filter_excel_paths([]) == []
    assert _filter_excel_paths(None) == []


def test_filter_excel_paths_case_insensitive():
    files = [r"C:\REPORT.XLSX", r"C:\old.XLS"]
    result = _filter_excel_paths(files)
    assert len(result) == 2


def test_filter_excel_paths_skips_undecodable_bytes():
    """Malformed bytes path is skipped, not raised."""
    files = [b"\xff\xfe\x00bogus", r"C:\good.xlsx"]
    result = _filter_excel_paths(files)
    # bogus may or may not survive Path() construction depending on platform;
    # the contract is "no exception escapes". The good path always survives.
    assert any(p.name == "good.xlsx" for p in result)


def test_log_dnd_crash_writes_to_home(tmp_path, monkeypatch):
    """Crash logger writes a one-line breadcrumb to ~/.hr-absensi-crash.log."""
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    _log_dnd_crash(ValueError("synthetic test crash"))
    log_path = tmp_path / ".hr-absensi-crash.log"
    assert log_path.exists()
    content = log_path.read_text(encoding="utf-8")
    assert "DnD" in content
    assert "ValueError" in content
    assert "synthetic test crash" in content


def test_log_dnd_crash_appends(tmp_path, monkeypatch):
    """Subsequent crashes append; no truncation."""
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    _log_dnd_crash(ValueError("first"))
    _log_dnd_crash(RuntimeError("second"))
    content = (tmp_path / ".hr-absensi-crash.log").read_text(encoding="utf-8")
    lines = [l for l in content.splitlines() if l.strip()]
    assert len(lines) == 2
    assert "first" in lines[0]
    assert "second" in lines[1]


def test_log_dnd_crash_never_raises(monkeypatch):
    """Even if writing the log itself fails, the function must not raise."""
    def boom(*args, **kwargs):
        raise OSError("disk full")
    # Force the log open to fail
    monkeypatch.setattr(Path, "open", boom, raising=False)
    # Should swallow the inner OSError, no exception bubbles up
    _log_dnd_crash(ValueError("anything"))
