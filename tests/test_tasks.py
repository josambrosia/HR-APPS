"""Tests for src.ui.tasks — run_bg background runner + BusyGuard.

The Tk loop is driven manually with root.update() in short bounded
loops (no free-running mainloop in tests).
"""
import threading
import time

import customtkinter as ctk

from src.ui.tasks import BusyGuard, run_bg


def _pump_until(root, cond, timeout=2.0) -> bool:
    """Drive the Tk loop until cond() is truthy or timeout (seconds)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        root.update()
        if cond():
            return True
        time.sleep(0.01)
    return bool(cond())


def _pump_for(root, seconds: float) -> None:
    """Drive the Tk loop for a fixed short duration."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        root.update()
        time.sleep(0.01)


# -- run_bg --

def test_run_bg_happy_path_delivers_result_and_progress(tk_root):
    progress_events = []
    done = {}

    def work(progress):
        progress(1, 3)
        progress(2, 3, label="tahap dua")
        return 42

    run_bg(
        tk_root, work,
        on_done=lambda r: done.setdefault("result", r),
        on_progress=lambda c, t, l: progress_events.append((c, t, l)),
        poll_ms=10,
    )
    assert _pump_until(tk_root, lambda: "result" in done)
    assert done["result"] == 42
    # Progress marshaled in order, before on_done, with label passthrough
    assert progress_events == [(1, 3, None), (2, 3, "tahap dua")]


def test_run_bg_error_path_delivers_exception(tk_root):
    caught = {}
    done = {}

    def work(progress):
        raise ValueError("boom")

    run_bg(
        tk_root, work,
        on_done=lambda r: done.setdefault("result", r),
        on_error=lambda exc: caught.setdefault("exc", exc),
        poll_ms=10,
    )
    assert _pump_until(tk_root, lambda: "exc" in caught)
    assert isinstance(caught["exc"], ValueError)
    assert str(caught["exc"]) == "boom"
    # Exactly one terminal callback — on_done must never fire
    _pump_for(tk_root, 0.1)
    assert done == {}


def test_run_bg_drops_callbacks_when_widget_destroyed(tk_root):
    frame = ctk.CTkFrame(tk_root)
    release = threading.Event()
    calls = []

    def work(progress):
        release.wait(1.0)
        return 7

    thread = run_bg(
        frame, work,
        on_done=lambda r: calls.append(("done", r)),
        on_error=lambda exc: calls.append(("error", exc)),
        poll_ms=10,
    )
    tk_root.update()
    frame.destroy()          # widget dies while the worker still runs
    release.set()
    thread.join(1.5)
    assert not thread.is_alive()
    _pump_for(tk_root, 0.2)  # give the (cancelled) poll loop a chance to misfire
    assert calls == []       # dropped silently — no callback, no error


def test_run_bg_worker_runs_off_main_thread(tk_root):
    seen = {}
    run_bg(
        tk_root,
        lambda progress: seen.setdefault("thread", threading.current_thread()),
        on_done=lambda r: seen.setdefault("done", True),
        poll_ms=10,
    )
    assert _pump_until(tk_root, lambda: "done" in seen)
    assert seen["thread"] is not threading.main_thread()


# -- BusyGuard --

def test_busy_guard_disables_and_restores(tk_root):
    b1 = ctk.CTkButton(tk_root, text="✓ Konfirmasi")
    b2 = ctk.CTkButton(tk_root, text="✕ Batal")
    guard = BusyGuard(b1, b2, busy_text="Memproses…")

    assert guard.acquire() is True
    assert guard.busy is True
    assert b1.cget("text") == "Memproses…"      # busy_text on primary only
    assert b1.cget("state") == "disabled"
    assert b2.cget("text") == "✕ Batal"
    assert b2.cget("state") == "disabled"

    guard.release()
    assert guard.busy is False
    assert b1.cget("text") == "✓ Konfirmasi"
    assert b1.cget("state") == "normal"
    assert b2.cget("state") == "normal"
    b1.destroy()
    b2.destroy()


def test_busy_guard_reentrancy_double_click_noops(tk_root):
    btn = ctk.CTkButton(tk_root, text="Simpan")
    guard = BusyGuard(btn, busy_text="Memproses…")
    assert guard.acquire() is True
    assert guard.acquire() is False      # double-click → caller no-ops
    guard.release()
    assert btn.cget("text") == "Simpan"  # first acquire's snapshot restored
    assert guard.acquire() is True       # usable again after release
    guard.release()
    btn.destroy()


def test_busy_guard_context_manager(tk_root):
    btn = ctk.CTkButton(tk_root, text="Terapkan Perubahan")
    guard = BusyGuard(btn)
    with guard:
        assert guard.busy is True
        assert btn.cget("state") == "disabled"
    assert guard.busy is False
    assert btn.cget("state") == "normal"
    btn.destroy()


def test_busy_guard_release_survives_destroyed_button(tk_root):
    btn = ctk.CTkButton(tk_root, text="X")
    guard = BusyGuard(btn)
    assert guard.acquire() is True
    btn.destroy()
    guard.release()  # must not raise even though the button is gone
    assert guard.busy is False
