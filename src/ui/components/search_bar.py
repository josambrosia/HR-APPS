"""Reusable search input — pill input with placeholder, clear button,
'N dari M' counter. Caller is responsible for the actual filtering
logic; this component only owns the input UI and emits on_change(query)
on every keystroke (or after a typing pause when debounce_ms > 0).
"""
from typing import Callable, Optional

import customtkinter as ctk

from src.ui.theme import (
    COLOR_BORDER, COLOR_SURFACE_HIGH,
    COLOR_TEXT, COLOR_TEXT_DIM, COLOR_TEXT_MUTED,
    FONT_BODY, FONT_SMALL,
    SPACE_XS, SPACE_SM,
    RADIUS_MD,
)


class SearchBar(ctk.CTkFrame):
    """Filter input bar with clear button and N-of-M counter.

    Layout: [🔍 input field] [✕] [12 dari 47]

    Caller passes on_change(query: str) which is invoked with the current
    query text — on every keystroke by default, or coalesced after a
    typing pause when `debounce_ms` > 0 (screens that rebuild whole
    treeviews per change use this so bursts of keystrokes cost one
    re-render). Clear (✕) and Escape flush immediately — they never wait
    out the debounce timer.

    NOTE on placeholder lifecycle: we deliberately do NOT use a
    textvariable here. CTkEntry's placeholder is suppressed when a
    bound StringVar fires a write trace during construction, which
    leaves the field looking blank. KeyRelease binding gives us the
    same per-keystroke callback without that side-effect.
    """

    def __init__(
        self,
        parent,
        on_change: Callable[[str], None],
        placeholder: str = "🔍 Cari karyawan...",
        width: int = 240,
        debounce_ms: int = 0,
        **kwargs,
    ):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self._on_change = on_change
        self._debounce_ms = int(debounce_ms)
        self._pending_after_id: Optional[str] = None

        self._entry = ctk.CTkEntry(
            self,
            placeholder_text=placeholder,
            placeholder_text_color=COLOR_TEXT_DIM,
            width=width, height=30,
            fg_color=COLOR_SURFACE_HIGH,
            border_color=COLOR_BORDER, border_width=1,
            text_color=COLOR_TEXT,
            font=FONT_BODY,
            corner_radius=RADIUS_MD,
        )
        self._entry.pack(side="left", padx=(0, SPACE_XS))
        self._entry.bind("<KeyRelease>", self._on_key_release)
        if self._debounce_ms > 0:
            # Escape flushes a pending debounced notification NOW so power
            # users never wait out the timer. Only bound in debounce mode —
            # debounce_ms=0 callers keep the exact pre-v22 behavior.
            self._entry.bind("<Escape>", self._flush_pending)

        self._clear_btn = ctk.CTkButton(
            self, text="✕", command=self.clear,
            width=28, height=30,
            fg_color="transparent",
            hover_color=COLOR_SURFACE_HIGH,
            text_color=COLOR_TEXT_MUTED,
            border_width=1, border_color=COLOR_BORDER,
            corner_radius=RADIUS_MD,
            font=FONT_SMALL,
        )
        self._clear_btn.pack(side="left", padx=(0, SPACE_SM))

        self._counter_label = ctk.CTkLabel(
            self, text="", font=FONT_SMALL,
            text_color=COLOR_TEXT_DIM,
        )
        self._counter_label.pack(side="left")

    def _on_key_release(self, _e=None):
        if self._debounce_ms <= 0:
            self._on_change(self.get())
            return
        # Debounce: every keystroke restarts the timer; only the pause
        # fires on_change, so rapid typing coalesces into one event.
        self._cancel_pending()
        self._pending_after_id = self.after(self._debounce_ms, self._fire_pending)

    def _cancel_pending(self) -> None:
        if self._pending_after_id is not None:
            try:
                self.after_cancel(self._pending_after_id)
            except Exception:
                pass
            self._pending_after_id = None

    def _fire_pending(self) -> None:
        self._pending_after_id = None
        try:
            if not self.winfo_exists():
                return  # timer outlived the widget (screen was switched)
        except Exception:
            return
        self._on_change(self.get())

    def _flush_pending(self, _e=None) -> None:
        """Deliver a pending debounced change immediately (Escape path)."""
        if self._pending_after_id is not None:
            self._cancel_pending()
            self._on_change(self.get())

    def get(self) -> str:
        return self._entry.get()

    def set(self, value: str) -> None:
        """Programmatically set the query value. Used by tests to
        simulate typing; production code should never call this.
        Always notifies immediately — never debounced."""
        self._entry.delete(0, "end")
        if value:
            self._entry.insert(0, value)
        self._cancel_pending()
        self._on_change(self.get())

    def clear(self) -> None:
        # A pending debounced notification would deliver a stale query
        # after the field is emptied — cancel it and notify "" NOW so the
        # clear feels instant.
        self._cancel_pending()
        self._entry.delete(0, "end")
        # Move focus away from the entry so CTkEntry naturally re-activates
        # its placeholder on the FocusOut event. Avoids the ghost-placeholder
        # bug where our manual _activate_placeholder() raced with CTkEntry's
        # internal placeholder state.
        try:
            self.winfo_toplevel().focus_set()
        except Exception:
            pass
        self._on_change("")

    def set_count(self, visible: int, total: int) -> None:
        if total == 0:
            self._counter_label.configure(text="")
        else:
            self._counter_label.configure(text=f"{visible} dari {total}")

    def focus(self) -> None:
        self._entry.focus_set()

    def install_shortcuts(self, host):
        """Wire Ctrl+F (focus this search) and click-outside-to-blur for the
        given host screen, with auto-cleanup on host <Destroy>.

        Centralizes what used to be a per-screen copy-pasted block. The blur
        decision is DEFERRED until after Tk's native click->focus handling so
        it can never steal focus from an input the user just clicked (the
        Resolve-form typing bug)."""
        self._host = host
        self._top = host.winfo_toplevel()
        host.bind("<Control-f>", self._focus_shortcut)
        try:
            self._top.bind_all("<Control-f>", self._focus_shortcut)
        except Exception:
            pass
        self._click_bind_id = self._top.bind(
            "<Button-1>", self._on_click_outside, add="+")
        host.bind("<Destroy>", self._on_host_destroy, add="+")

    def _focus_shortcut(self, _e=None):
        if self.winfo_exists():
            self.focus()
        return "break"

    def _on_click_outside(self, event):
        # Click inside the search bar? Leave it entirely alone.
        w = event.widget
        while w is not None:
            if w is self:
                return
            w = getattr(w, "master", None)
        # Outside: defer the decision so Tk's native click->focus runs first.
        try:
            self.after_idle(self._release_if_orphaned)
        except Exception:
            pass

    def _release_if_orphaned(self):
        try:
            focused = self.focus_get()
        except Exception:
            return
        w = focused
        while w is not None:
            if w is self:
                # Focus is STILL inside the search -> inert click -> blur to host.
                try:
                    self._host.focus_set()
                except Exception:
                    pass
                return
            w = getattr(w, "master", None)
        # Focus already moved to another real widget -> leave it untouched.

    def _on_host_destroy(self, _e=None):
        try:
            self._top.unbind_all("<Control-f>")
        except Exception:
            pass
        try:
            if getattr(self, "_click_bind_id", None):
                self._top.unbind("<Button-1>", self._click_bind_id)
                self._click_bind_id = None
        except Exception:
            pass
