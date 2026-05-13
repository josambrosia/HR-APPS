"""Drag-and-drop file hook for Tk widgets on Windows.

Drop-in replacement for the `windnd` library. windnd has a stack-buffer-
overrun bug: it passes `ctypes.sizeof(szFile)` (byte size = 520) as the
`cch` parameter to `DragQueryFileW`, but `cch` is documented as character
count (should be 260 for a 260-wchar buffer). For dropped paths long
enough to make Windows write past the buffer, the stack canary trips and
the process is killed via `__fastfail(0xc0000409)` — completely
bypassing Python try/except.

This implementation follows the MSDN-canonical pattern:
  1. Call `DragQueryFileW(hdrop, i, NULL, 0)` to get required name length
  2. Allocate exactly `(name_len + 1) * sizeof(wchar_t)` bytes
  3. Call `DragQueryFileW(hdrop, i, buf, name_len + 1)` — pass CHAR count
  4. `DragFinish(hdrop)` exactly once

The user callback receives a list of str (paths). Callback is invoked
SYNCHRONOUSLY from inside the Win32 WNDPROC for WM_DROPFILES — heavy work
(Tk widget manipulation, DB writes, modal dialogs) MUST be deferred via
`widget.after(0, ...)` to avoid re-entrant message-pump issues.

Any exception raised by the user callback (or in our hook code itself)
is caught and logged to `~/.hr-absensi-crash.log`. The packaged .exe is
windowed (runw.exe bootloader) so stderr goes /dev/null — file logging
is the only way to leave a breadcrumb.
"""
import ctypes
import platform
from datetime import datetime
from pathlib import Path
from typing import Callable, List

WM_DROPFILES = 0x0233
GWL_WNDPROC = -4

_is_64bit = platform.architecture()[0] == "64bit"
_LONG_PTR = ctypes.c_int64 if _is_64bit else ctypes.c_long
_GetWindowLongPtr = (
    ctypes.windll.user32.GetWindowLongPtrW if _is_64bit
    else ctypes.windll.user32.GetWindowLongW
)
_SetWindowLongPtr = (
    ctypes.windll.user32.SetWindowLongPtrW if _is_64bit
    else ctypes.windll.user32.SetWindowLongW
)
_WNDPROC_TYPE = ctypes.WINFUNCTYPE(
    _LONG_PTR, _LONG_PTR, ctypes.c_uint, _LONG_PTR, _LONG_PTR,
)

# Module-level registry: hwnd -> {"proc": WNDPROC ref, "callback": fn, "old": old proc ptr}
# Holding refs is CRITICAL: ctypes will GC the WNDPROC wrapper otherwise, leaving
# Windows holding a dangling pointer that crashes on the next message.
_hooks: dict = {}


def _log(exc: Exception, where: str = "") -> None:
    """Append a one-line crash breadcrumb to ~/.hr-absensi-crash.log."""
    try:
        log_path = Path.home() / ".hr-absensi-crash.log"
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(
                f"[{datetime.now().isoformat()}] DnD/{where}: "
                f"{type(exc).__name__}: {exc}\n"
            )
    except Exception:
        pass  # logging must never raise


def _read_drop_files(hdrop) -> List[str]:
    """Read all file paths from an HDROP using the MSDN-canonical pattern.

    Queries each file's required name length first, allocates exactly the
    needed buffer, then reads with the correct char-count. Handles paths
    of any length (including long-path support up to 32K chars).
    """
    DragQueryFileW = ctypes.windll.shell32.DragQueryFileW
    count = DragQueryFileW(hdrop, 0xFFFFFFFF, None, 0)
    files = []
    for i in range(count):
        # Phase 1: query required name length (chars, excluding NULL)
        name_len = DragQueryFileW(hdrop, i, None, 0)
        if name_len <= 0:
            continue
        # Phase 2: allocate exact buffer (name_len + 1 chars for NULL terminator)
        buf = ctypes.create_unicode_buffer(name_len + 1)
        # Phase 3: read — cch parameter is CHARACTER COUNT, not byte size
        DragQueryFileW(hdrop, i, buf, name_len + 1)
        files.append(buf.value)
    return files


def hook_dropfiles(widget, callback: Callable[[List[str]], None]) -> None:
    """Install a file-drop hook on the given Tk widget.

    Replaces the widget's WNDPROC with one that intercepts WM_DROPFILES,
    extracts the dropped file paths, and invokes `callback(paths)`. All
    other messages pass through unchanged.

    The hook persists for the widget's lifetime. Multiple calls on the
    same widget replace any prior hook (last wins).

    Args:
        widget: a Tk widget with `winfo_id()` (any tk/CTk widget)
        callback: receives `list[str]` of dropped paths. Exceptions are
            caught and logged; they do not propagate back to the WNDPROC.
    """
    try:
        hwnd = widget.winfo_id()
    except Exception as e:
        _log(e, "hook_dropfiles.winfo_id")
        return

    def wndproc(hwnd_arg, msg, wp, lp):
        # State lookup by the captured hwnd (closure)
        state = _hooks.get(hwnd)
        if state is None:
            # Hook was unregistered (shouldn't normally happen); pass-through
            return ctypes.windll.user32.DefWindowProcW(hwnd_arg, msg, wp, lp)

        if msg == WM_DROPFILES:
            hdrop = wp
            files = []
            try:
                files = _read_drop_files(hdrop)
            except Exception as e:
                _log(e, "read_drop_files")
            finally:
                # Always release the drop, even on failure
                try:
                    ctypes.windll.shell32.DragFinish(hdrop)
                except Exception as e:
                    _log(e, "DragFinish")
            if files:
                try:
                    state["callback"](files)
                except Exception as e:
                    _log(e, "user_callback")
            return 0

        # Pass-through to original WNDPROC for all other messages
        try:
            return ctypes.windll.user32.CallWindowProcW(
                state["old"], hwnd_arg, msg, wp, lp,
            )
        except Exception as e:
            _log(e, "CallWindowProcW")
            return ctypes.windll.user32.DefWindowProcW(hwnd_arg, msg, wp, lp)

    proc_ref = _WNDPROC_TYPE(wndproc)

    try:
        ctypes.windll.shell32.DragAcceptFiles(hwnd, True)
        old_wndproc = _GetWindowLongPtr(hwnd, GWL_WNDPROC)
        _SetWindowLongPtr(hwnd, GWL_WNDPROC, proc_ref)
    except Exception as e:
        _log(e, "hook_install")
        return

    # Pin references so GC doesn't collect them (otherwise Windows calls
    # a dangling pointer on the next message → crash)
    _hooks[hwnd] = {
        "proc": proc_ref,
        "callback": callback,
        "old": old_wndproc,
    }
