"""v20 signature: a tiny per-employee attendance dot-strip, colored by the
Heatmap palette, shown as a Treeview row image in Ranking Lengkap."""
from PIL import Image, ImageDraw
from src.core.heatmap import STATUS_COLORS

_SCALE = 3  # render at 3x then downscale for crisp edges


def render_strip(statuses, *, cell=7, gap=2, pad=2):
    """statuses: ordered list of status keys (workdays only, weekends excluded).
    Returns a PIL RGBA Image: a horizontal row of rounded dots, one per status,
    each filled with STATUS_COLORS[status] (unknown keys -> transparent)."""
    n = max(1, len(statuses))
    w = pad * 2 + n * cell + (n - 1) * gap
    h = pad * 2 + cell
    img = Image.new("RGBA", (w * _SCALE, h * _SCALE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = _SCALE
    x = pad * s
    for st in statuses:
        hexc = STATUS_COLORS.get(st)
        if hexc:
            rgb = tuple(int(hexc[i:i + 2], 16) for i in (1, 3, 5))
            d.rounded_rectangle([x, pad * s, x + cell * s, pad * s + cell * s],
                                 radius=2 * s, fill=rgb + (255,))
        x += (cell + gap) * s
    return img.resize((w, h), Image.LANCZOS)


def month_status_map(conn, month):
    """Return {employee_id: [status_key, ...]} for workdays of `month`,
    reusing the Heatmap context so colors/logic match exactly. Weekend/holiday
    days (status 'libur') are excluded so the strip shows only workdays."""
    from src.core.heatmap import build_heatmap_context
    ctx = build_heatmap_context(conn, month, exclude_outliers=False)
    out = {}
    for emp in ctx["employees"]:
        # cells is a dict keyed by day number (int); iterate in day order
        statuses = [emp["cells"][d]["status"]
                    for d in sorted(emp["cells"].keys())
                    if emp["cells"][d]["status"] != "libur"]
        out[emp["employee_id"]] = statuses
    return out
