"""Tests for src.ui.components.dnd_hook.

The Win32 WNDPROC subclassing path itself can't be unit-tested without a
real window. But we CAN test the path-reading helper that consumes
DragQueryFileW results — that's where the windnd bug lived.
"""
import ctypes
from unittest.mock import MagicMock, patch

import pytest


def _make_drag_query_mock(file_paths: list):
    """Build a mock DragQueryFileW that mimics the real API.

    Real signature: DragQueryFileW(hDrop, iFile, lpszFile, cch) -> UINT
      - iFile=0xFFFFFFFF: returns count of files (lpszFile/cch ignored)
      - lpszFile=None, cch=0: returns required name length (chars, no NULL)
      - otherwise: copies up to cch chars into lpszFile, returns chars copied
    """
    def fake_DragQueryFileW(hdrop, iFile, lpszFile, cch):
        if iFile == 0xFFFFFFFF:
            return len(file_paths)
        if iFile >= len(file_paths):
            return 0
        path = file_paths[iFile]
        if lpszFile is None or cch == 0:
            return len(path)  # name length (excluding NULL)
        # Write path into the buffer (it's a ctypes c_wchar_array)
        try:
            for j, ch in enumerate(path):
                if j >= cch - 1:
                    break
                lpszFile[j] = ch
            lpszFile[min(len(path), cch - 1)] = "\x00"
        except Exception:
            pass
        return min(len(path), cch - 1)
    return fake_DragQueryFileW


def test_read_drop_files_single_short_path():
    from src.ui.components import dnd_hook
    with patch.object(ctypes.windll.shell32, "DragQueryFileW",
                      _make_drag_query_mock([r"C:\test.xlsx"])):
        result = dnd_hook._read_drop_files(hdrop=12345)
    assert result == [r"C:\test.xlsx"]


def test_read_drop_files_multiple():
    from src.ui.components import dnd_hook
    paths = [r"C:\a.xlsx", r"C:\b.xls", r"D:\nested\folder\c.xlsx"]
    with patch.object(ctypes.windll.shell32, "DragQueryFileW",
                      _make_drag_query_mock(paths)):
        result = dnd_hook._read_drop_files(hdrop=12345)
    assert result == paths


def test_read_drop_files_long_path():
    """A 300-character path must not overflow (this was the windnd crash)."""
    from src.ui.components import dnd_hook
    long_path = "C:\\" + ("a" * 295) + ".xlsx"
    assert len(long_path) > 260
    with patch.object(ctypes.windll.shell32, "DragQueryFileW",
                      _make_drag_query_mock([long_path])):
        result = dnd_hook._read_drop_files(hdrop=12345)
    assert result == [long_path]


def test_read_drop_files_empty():
    from src.ui.components import dnd_hook
    with patch.object(ctypes.windll.shell32, "DragQueryFileW",
                      _make_drag_query_mock([])):
        result = dnd_hook._read_drop_files(hdrop=12345)
    assert result == []


def test_read_drop_files_skips_zero_length_entry():
    """Defensive: if DragQueryFileW reports name_len=0 for an entry, skip it."""
    from src.ui.components import dnd_hook

    def weird_mock(hdrop, iFile, lpszFile, cch):
        if iFile == 0xFFFFFFFF:
            return 2
        if iFile == 0:
            return 0  # claims zero-length name — should be skipped
        if iFile == 1:
            path = r"C:\real.xlsx"
            if lpszFile is None or cch == 0:
                return len(path)
            for j, ch in enumerate(path):
                if j >= cch - 1:
                    break
                lpszFile[j] = ch
            return len(path)
        return 0

    with patch.object(ctypes.windll.shell32, "DragQueryFileW", weird_mock):
        result = dnd_hook._read_drop_files(hdrop=12345)
    # Only the real entry survives
    assert result == [r"C:\real.xlsx"]


def test_log_writes_breadcrumb(tmp_path, monkeypatch):
    from pathlib import Path
    from src.ui.components import dnd_hook
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    dnd_hook._log(ValueError("synthetic"), where="unit-test")
    log_path = tmp_path / ".hr-absensi-crash.log"
    assert log_path.exists()
    content = log_path.read_text(encoding="utf-8")
    assert "DnD/unit-test" in content
    assert "ValueError" in content
    assert "synthetic" in content


def test_log_never_raises(monkeypatch):
    """Even if file write fails, log() must not propagate."""
    from pathlib import Path
    from src.ui.components import dnd_hook

    def boom(*args, **kwargs):
        raise OSError("disk full")
    monkeypatch.setattr(Path, "open", boom, raising=False)
    dnd_hook._log(ValueError("anything"), where="boom-test")


def test_hooks_registry_pins_callback():
    """Hooks dict must hold a ref to the user callback (otherwise GC would
    drop it and the WNDPROC would call a dead reference → crash)."""
    from src.ui.components import dnd_hook
    # Synthesize a registration without going through hook_dropfiles (which
    # needs a real Win32 window).
    fake_hwnd = 99999
    cb = lambda files: None  # noqa: E731
    proc_ref = object()  # placeholder
    dnd_hook._hooks[fake_hwnd] = {"proc": proc_ref, "callback": cb, "old": 0}
    try:
        assert dnd_hook._hooks[fake_hwnd]["callback"] is cb
        assert dnd_hook._hooks[fake_hwnd]["proc"] is proc_ref
    finally:
        del dnd_hook._hooks[fake_hwnd]
