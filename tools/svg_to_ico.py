"""Convert assets/brand/icon-04E.svg to multi-resolution .ico file.

Uses cairosvg to rasterize SVG → PNG at multiple sizes, then Pillow to
bundle into a Windows .ico with embedded sizes.

Run from project root:
    python tools/svg_to_ico.py

Output: assets/brand/icon-04E.ico (multi-res: 16, 32, 48, 64, 128, 256)
"""
import sys
from io import BytesIO
from pathlib import Path

try:
    import cairosvg
except ImportError as e:
    print("ERROR: cairosvg not installed. Run: pip install cairosvg",
          file=sys.stderr)
    print(f"Underlying error: {e}", file=sys.stderr)
    sys.exit(1)

from PIL import Image


SVG_PATH = Path("assets/brand/icon-04E.svg")
ICO_PATH = Path("assets/brand/icon-04E.ico")
SIZES = [16, 32, 48, 64, 128, 256]


def render_svg_to_png(svg_path: Path, size: int) -> Image.Image:
    """Rasterize SVG to PNG at given size, return as PIL.Image."""
    png_bytes = cairosvg.svg2png(
        url=str(svg_path),
        output_width=size,
        output_height=size,
    )
    return Image.open(BytesIO(png_bytes)).convert("RGBA")


def main():
    if not SVG_PATH.exists():
        print(f"ERROR: source not found: {SVG_PATH}", file=sys.stderr)
        sys.exit(1)

    # Pillow can save .ico with multi-resolution by passing sizes= param
    # The base image must be the largest size; Pillow downsamples internally.
    base = render_svg_to_png(SVG_PATH, max(SIZES))
    base.save(
        ICO_PATH,
        format="ICO",
        sizes=[(s, s) for s in SIZES],
    )
    print(f"Wrote {ICO_PATH} ({ICO_PATH.stat().st_size} bytes, "
          f"sizes: {SIZES})")


if __name__ == "__main__":
    main()
