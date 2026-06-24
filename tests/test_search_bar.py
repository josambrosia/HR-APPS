"""Tests for src.ui.components.search_bar — reusable filter input."""
from src.ui.components.search_bar import SearchBar


def test_search_bar_constructs(tk_root):
    captured = []
    bar = SearchBar(tk_root, on_change=captured.append)
    tk_root.update_idletasks()
    assert bar is not None
    assert bar.get() == ""
    bar.destroy()


def test_search_bar_callback_fires_on_typing(tk_root):
    captured = []
    bar = SearchBar(tk_root, on_change=captured.append)
    tk_root.update_idletasks()
    bar.set("budi")
    tk_root.update_idletasks()
    assert captured[-1] == "budi"
    assert bar.get() == "budi"
    bar.destroy()


def test_search_bar_clear_resets_and_fires(tk_root):
    captured = []
    bar = SearchBar(tk_root, on_change=captured.append)
    tk_root.update_idletasks()
    bar.set("budi")
    tk_root.update_idletasks()
    bar.clear()
    tk_root.update_idletasks()
    assert bar.get() == ""
    assert captured[-1] == ""
    bar.destroy()


def test_search_bar_set_count_updates_label(tk_root):
    bar = SearchBar(tk_root, on_change=lambda _q: None)
    tk_root.update_idletasks()
    bar.set_count(visible=12, total=47)
    tk_root.update_idletasks()
    assert "12" in bar._counter_label.cget("text")
    assert "47" in bar._counter_label.cget("text")
    bar.destroy()


import customtkinter as ctk


def test_install_shortcuts_blurs_when_focus_stays_in_search(tk_root, monkeypatch):
    """Inert click outside search (focus still in search) -> blur to host."""
    host = ctk.CTkFrame(tk_root)
    bar = SearchBar(host, on_change=lambda _q: None)
    bar.install_shortcuts(host)
    tk_root.update_idletasks()
    monkeypatch.setattr(bar, "focus_get", lambda: bar)   # focus still in the search
    blurred = []
    monkeypatch.setattr(host, "focus_set", lambda: blurred.append(True))
    bar._release_if_orphaned()
    assert blurred == [True]
    host.destroy()


def test_install_shortcuts_leaves_focus_on_other_input(tk_root, monkeypatch):
    """Click landed on another input (focus moved out) -> do NOT steal it."""
    host = ctk.CTkFrame(tk_root)
    other = ctk.CTkEntry(host)
    bar = SearchBar(host, on_change=lambda _q: None)
    bar.install_shortcuts(host)
    tk_root.update_idletasks()
    monkeypatch.setattr(bar, "focus_get", lambda: other)   # focus on a different widget
    blurred = []
    monkeypatch.setattr(host, "focus_set", lambda: blurred.append(True))
    bar._release_if_orphaned()
    assert blurred == []
    host.destroy()


def test_install_shortcuts_installs_and_cleans_up(tk_root):
    host = ctk.CTkFrame(tk_root)
    bar = SearchBar(host, on_change=lambda _q: None)
    bar.install_shortcuts(host)
    tk_root.update_idletasks()
    assert bar._click_bind_id is not None
    assert host.bind("<Control-f>") != ""
    bar._on_host_destroy()
    assert bar._click_bind_id is None
    host.destroy()
