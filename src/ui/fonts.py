"""v20 — load the bundled display typeface (Space Grotesk) at runtime without
installing it system-wide, then repoint the theme's display tokens at it.

Falls back silently to the default UI family (Segoe UI) if the font can't be
loaded — non-Windows, missing file, or GDI failure. The app never depends on
the font being present; titles simply render in Segoe UI on fallback.
"""

_FR_PRIVATE = 0x10
_FONT_FILES = (
    "SpaceGrotesk-Bold.ttf",
    "SpaceGrotesk-Medium.ttf",
    "SpaceGrotesk-SemiBold.ttf",
)
_DISPLAY_FAMILY = "Space Grotesk"


def _load_ttfs() -> bool:
    """Register the bundled TTFs with GDI for this process (private scope).
    Returns True if at least one font loaded. Verified: Tk sees FR_PRIVATE
    fonts on this Windows build."""
    try:
        import ctypes
        from src.config import RESOURCE_ROOT
        font_dir = RESOURCE_ROOT / "assets" / "fonts"
        added = 0
        for fn in _FONT_FILES:
            p = font_dir / fn
            if p.exists():
                added += ctypes.windll.gdi32.AddFontResourceExW(str(p), _FR_PRIVATE, 0)
        return added > 0
    except Exception:
        return False


def apply_display_font() -> str:
    """Load the display font and repoint the theme's display tokens at it.
    Returns the resolved family ('Space Grotesk' on success, else 'Segoe UI').
    Call ONCE at startup BEFORE any screen is built (screens import the theme
    tokens lazily, so they pick up the rebuilt tuples)."""
    family = _DISPLAY_FAMILY if _load_ttfs() else "Segoe UI"
    try:
        import src.ui.theme as theme
        theme.FONT_DISPLAY_FAMILY = family
        theme.FONT_KPI = (family, 28, "bold")
        theme.FONT_DISPLAY = (family, 24, "bold")
        theme.FONT_HEADING = (family, 18, "bold")
    except Exception:
        pass
    return family
