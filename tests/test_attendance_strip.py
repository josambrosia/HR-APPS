from PIL import Image
from src.ui.components.attendance_strip import render_strip


def test_render_strip_returns_image_sized_by_count():
    img = render_strip(["hadir", "sedang", "parah", "mangkir"])
    assert isinstance(img, Image.Image)
    assert img.mode == "RGBA"
    # width grows with the number of days; non-empty
    assert img.width > 0 and img.height > 0
    w4 = render_strip(["hadir"] * 4).width
    w8 = render_strip(["hadir"] * 8).width
    assert w8 > w4


def test_render_strip_colors_match_palette():
    from src.core.heatmap import STATUS_COLORS
    img = render_strip(["hadir"])  # single emerald dot
    rgb = tuple(int(STATUS_COLORS["hadir"][i:i + 2], 16) for i in (1, 3, 5))
    # at least one pixel equals the hadir color
    px = img.convert("RGBA").getdata()
    assert any(p[:3] == rgb for p in px)
