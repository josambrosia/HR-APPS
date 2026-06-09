def test_heatmap_screen_open_dashboard(tk_root, temp_db_path, monkeypatch):
    from src.db.schema import init_db
    import src.ui.screens.heatmap as mod
    init_db(temp_db_path)
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    monkeypatch.setattr(mod.heatmap_server, "ensure_started",
                        lambda: "http://127.0.0.1:9999")
    calls = []
    monkeypatch.setattr(mod, "open_html_in_browser", lambda url: calls.append(url))
    s = mod.HeatmapScreen(tk_root)
    tk_root.update_idletasks()
    assert hasattr(s, "_open_print")
    s._open_dashboard()
    assert calls and calls[0].startswith("http://127.0.0.1:9999/heatmap?month=")
    s.destroy()
