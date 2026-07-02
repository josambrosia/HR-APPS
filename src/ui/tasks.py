"""Background-task runner — heavy work off the Tk main thread, no freeze.

run_bg() runs `work` in a daemon thread and marshals progress / result /
error back to the main thread through a queue.Queue drained by a
widget.after() polling loop. Tk is single-threaded: NOTHING here touches
a widget from the worker thread — all callbacks (on_progress / on_done /
on_error) fire on the main thread.

Database rule (sanctioned pattern): a worker MAY open its own SQLite
connection inside `work` via the existing context manager

    from src.db.connection import get_connection
    with get_connection(DB_PATH) as conn:
        ...

because get_connection creates a FRESH connection per use. NEVER pass a
sqlite3.Connection between threads — connections are bound to the thread
that created them.

Typical screen wiring:

    if not self._guard.acquire():
        return  # double-click — operation already running
    run_bg(
        self,
        work=lambda progress: do_heavy_thing(progress),
        on_done=lambda result: (self._guard.release(), self._render(result)),
        on_error=lambda exc: (self._guard.release(), feedback.show_error(...)),
        on_progress=lambda cur, total, label: self._bar.set(cur / total),
    )
"""
import queue
import threading
import tkinter as tk
from typing import Callable, Optional


def run_bg(
    widget,
    work: Callable,
    *,
    on_done: Callable,
    on_error: Optional[Callable] = None,
    on_progress: Optional[Callable] = None,
    poll_ms: int = 50,
) -> threading.Thread:
    """Run `work(progress)` in a daemon thread; deliver callbacks on the
    Tk main thread via `widget.after` polling.

    Args:
        widget: any live Tk widget — owns the polling loop. If it gets
            destroyed mid-flight, polling stops and ALL remaining
            callbacks are dropped silently (the thread still finishes).
        work: callable taking one argument `progress`; the worker may
            call `progress(current, total, label=None)` any number of
            times to report progress.
        on_done: called once with work's return value on success.
        on_error: called once with the exception if work raises. If None,
            the exception is re-raised on the main thread (surfaces via
            Tk's callback-exception reporting).
        on_progress: called as on_progress(current, total, label) for
            each progress() call, in order, before the terminal callback.
        poll_ms: queue polling interval in milliseconds.

    Returns the started Thread (daemon) — callers normally ignore it;
    tests may join() it.
    """
    q: queue.Queue = queue.Queue()
    state = {"after_id": None}
    widget_path = str(widget)

    def _progress(current, total, label=None):
        q.put(("progress", (current, total, label)))

    def _worker():
        try:
            result = work(_progress)
        except Exception as exc:
            q.put(("error", exc))
        else:
            q.put(("done", result))

    def _widget_alive() -> bool:
        try:
            return bool(widget.winfo_exists())
        except tk.TclError:
            return False

    def _on_widget_destroy(event):
        # A toplevel's bindtags receive <Destroy> for every child too —
        # only react to the widget itself. Compare Tcl paths: event.widget
        # may be a plain string mid-teardown.
        if str(event.widget) != widget_path:
            return
        if state["after_id"] is not None:
            try:
                widget.after_cancel(state["after_id"])
            except tk.TclError:
                pass
            state["after_id"] = None

    def _poll():
        state["after_id"] = None
        if not _widget_alive():
            return  # widget destroyed — drop callbacks silently
        while True:
            try:
                kind, payload = q.get_nowait()
            except queue.Empty:
                break
            if kind == "progress":
                if on_progress is not None:
                    current, total, label = payload
                    on_progress(current, total, label)
            elif kind == "done":
                on_done(payload)
                return  # terminal — stop polling
            else:  # "error"
                if on_error is not None:
                    on_error(payload)
                    return
                raise payload  # no handler — surface on main thread
        try:
            state["after_id"] = widget.after(poll_ms, _poll)
        except tk.TclError:
            pass  # widget destroyed between drain and reschedule

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    # Cancel the pending poll timer the moment the widget dies — without
    # this, one orphaned after-command per abandoned task would fire into
    # a deleted Tcl command and spam bgerror noise. Bind via tk.Misc
    # directly: CTk widgets delegate .bind() to an internal canvas, which
    # would put the handler on the wrong widget.
    tk.Misc.bind(widget, "<Destroy>", _on_widget_destroy, add="+")
    state["after_id"] = widget.after(poll_ms, _poll)
    return thread


class BusyGuard:
    """Disable a set of CTkButtons while an operation runs; restore after.

    Saves each button's text + state on acquire(), sets them disabled
    (the FIRST button — the primary CTA — also gets `busy_text` if
    given), and restores everything on release(). Re-entrancy safe:
    acquire() returns False when already busy, so double-clicks no-op.

    Two usage styles:

        # async (with run_bg) — release in on_done/on_error:
        if not guard.acquire():
            return
        run_bg(..., on_done=lambda r: (guard.release(), ...))

        # sync block:
        with guard:          # no-op passthrough if already busy
            do_short_work()
    """

    def __init__(self, *buttons, busy_text: Optional[str] = None):
        self._buttons = list(buttons)
        self._busy_text = busy_text
        self._busy = False
        self._saved: list = []          # [(btn, text, state), ...]
        self._enter_acquired: list = []  # stack — nested `with` safe

    @property
    def busy(self) -> bool:
        return self._busy

    def acquire(self) -> bool:
        """Disable the buttons. Returns False (no-op) if already busy."""
        if self._busy:
            return False
        self._busy = True
        self._saved = []
        for i, btn in enumerate(self._buttons):
            try:
                self._saved.append((btn, btn.cget("text"), btn.cget("state")))
                if self._busy_text is not None and i == 0:
                    btn.configure(state="disabled", text=self._busy_text)
                else:
                    btn.configure(state="disabled")
            except tk.TclError:
                continue  # button already destroyed — skip it
        return True

    def release(self) -> None:
        """Restore original text + state. Safe to call when not busy."""
        if not self._busy:
            return
        for btn, text, state in self._saved:
            try:
                btn.configure(text=text, state=state)
            except tk.TclError:
                continue  # button destroyed during the operation
        self._saved = []
        self._busy = False

    def __enter__(self):
        self._enter_acquired.append(self.acquire())
        return self

    def __exit__(self, *_exc):
        if self._enter_acquired and self._enter_acquired.pop():
            self.release()
        return False
