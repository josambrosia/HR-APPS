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
    bar._query_var.set("budi")
    tk_root.update_idletasks()
    assert captured[-1] == "budi"
    assert bar.get() == "budi"
    bar.destroy()


def test_search_bar_clear_resets_and_fires(tk_root):
    captured = []
    bar = SearchBar(tk_root, on_change=captured.append)
    tk_root.update_idletasks()
    bar._query_var.set("budi")
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
