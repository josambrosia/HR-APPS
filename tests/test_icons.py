from src.ui import icons


def test_glyphs_cover_all_nav_screen_keys():
    expected = {
        "Dashboard", "Heatmap", "Import", "Export", "ActiveMonth", "Issues",
        "SevereLateness", "WhatsAppAssistant", "Coaching", "Outlier",
        "Holiday", "Settings", "About",
    }
    assert expected <= set(icons.GLYPHS)
    # every glyph is a single Private-Use-Area char (valid icon-font codepoint)
    for k, v in icons.GLYPHS.items():
        assert len(v) == 1 and 0xE000 <= ord(v) <= 0xF8FF, k


def test_glyph_falls_back_to_empty_when_no_icon_font(monkeypatch):
    monkeypatch.setattr(icons, "_resolved_font", "")
    assert icons.glyph("Dashboard") == ""   # caller then uses its emoji


def test_glyph_returns_char_when_font_available(monkeypatch):
    monkeypatch.setattr(icons, "_resolved_font", "Segoe Fluent Icons")
    assert icons.glyph("Dashboard") == icons.GLYPHS["Dashboard"]
    assert icons.glyph("NotARealKey") == ""
