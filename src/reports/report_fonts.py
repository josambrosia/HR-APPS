"""Embed the bundled Space Grotesk display face as base64 @font-face CSS so the
browser-rendered report PDFs render in the app's own display typeface instead of
a system fallback. Read once per process (lru_cache). Returns "" on any failure,
in which case the templates fall back to their Segoe UI stack."""
import base64
from functools import lru_cache

# (css font-family, weight, bundled filename)
_FACES = (
    ("Space Grotesk", 500, "SpaceGrotesk-Medium.ttf"),
    ("Space Grotesk", 700, "SpaceGrotesk-Bold.ttf"),
)


@lru_cache(maxsize=1)
def display_font_face_css() -> str:
    """Return @font-face rules (with base64 data URIs) for Space Grotesk, or ""
    if the bundled TTFs can't be read."""
    try:
        from src.config import RESOURCE_ROOT
        font_dir = RESOURCE_ROOT / "assets" / "fonts"
        rules = []
        for family, weight, fn in _FACES:
            p = font_dir / fn
            if not p.exists():
                continue
            b64 = base64.b64encode(p.read_bytes()).decode("ascii")
            rules.append(
                f"@font-face{{font-family:'{family}';font-weight:{weight};"
                f"font-style:normal;font-display:swap;"
                f"src:url(data:font/ttf;base64,{b64}) format('truetype');}}"
            )
        return "\n".join(rules)
    except Exception:
        return ""
