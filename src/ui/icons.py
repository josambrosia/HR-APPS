"""v20 — monochrome sidebar icons via the Windows **Segoe Fluent Icons** font.

Codepoints were verified visually against the installed font. Falls back to
**Segoe MDL2 Assets** (most codepoints shared), and finally to the caller's
emoji, so the app stays usable on any Windows build or platform.

Icons are font glyphs (not images): render with
`ctk.CTkLabel(text=glyph(key), font=(icon_font(), size), text_color=...)`.
"""

_PRIMARY_FONT = "Segoe Fluent Icons"
_FALLBACK_FONT = "Segoe MDL2 Assets"

# screen_key -> Fluent codepoint (verified). Keys match HRApp nav screen keys.
GLYPHS = {
    "Dashboard":         "",  # dashboard panels
    "Heatmap":           "",  # grid
    "Import":            "",  # download
    "Export":            "",  # upload
    "ActiveMonth":       "",  # calendar
    "Issues":            "",  # flag
    "SevereLateness":    "",  # clock
    "WhatsAppAssistant": "",  # chat bubbles
    "Coaching":          "",  # target / bullseye
    "Outlier":           "",  # filter
    "Holiday":           "",  # sun
    "Settings":          "",  # gear
    "About":             "",  # info
}

_resolved_font = None  # cached after first resolve


def icon_font() -> str:
    """Resolve the icon font family once: Fluent -> MDL2 -> "" (unavailable).
    Requires a Tk root to exist; returns "" if not (caller keeps its emoji)."""
    global _resolved_font
    if _resolved_font is not None:
        return _resolved_font
    try:
        import tkinter.font as tkfont
        fams = set(tkfont.families())
        if _PRIMARY_FONT in fams:
            _resolved_font = _PRIMARY_FONT
        elif _FALLBACK_FONT in fams:
            _resolved_font = _FALLBACK_FONT
        else:
            _resolved_font = ""
    except Exception:
        _resolved_font = ""
    return _resolved_font


def glyph(key: str) -> str:
    """Return the icon glyph char for a nav screen key, or "" when the icon
    font (or the key) is unavailable — callers fall back to their emoji."""
    if not icon_font():
        return ""
    return GLYPHS.get(key, "")
