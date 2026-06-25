import sys
from src.ui import fonts


def test_apply_display_font_contract_and_isolation():
    """apply_display_font() resolves a family and repoints ONLY the display
    tokens; body/data fonts are untouched. Saves/restores theme globals so the
    mutation doesn't leak into other tests."""
    import src.ui.theme as theme
    saved = (theme.FONT_DISPLAY_FAMILY, theme.FONT_DISPLAY,
             theme.FONT_HEADING, theme.FONT_KPI)
    try:
        fam = fonts.apply_display_font()
        assert isinstance(fam, str) and fam
        assert theme.FONT_DISPLAY[0] == fam
        assert theme.FONT_HEADING[0] == fam
        assert theme.FONT_KPI[0] == fam
        # body / label / mono are NOT changed by the display font
        assert theme.FONT_BODY[0] == "Segoe UI"
        assert theme.FONT_MONO_DATA[0] == "Consolas"
        # On Windows with the TTFs bundled the display face actually loads.
        from src.config import RESOURCE_ROOT
        ttf = RESOURCE_ROOT / "assets" / "fonts" / "SpaceGrotesk-Bold.ttf"
        if sys.platform == "win32" and ttf.exists():
            assert fam == "Space Grotesk"
    finally:
        (theme.FONT_DISPLAY_FAMILY, theme.FONT_DISPLAY,
         theme.FONT_HEADING, theme.FONT_KPI) = saved
