"""Render the Heatmap print report (matrix + appendix) to an HTML string.

Server-free: mirrors the old loopback route, reusing the reports Jinja2 env so
template paths resolve in dev AND the PyInstaller bundle. The caller writes the
string to a temp file and opens it in the browser (Ctrl-P / Save PDF)."""
from datetime import date

from src.db.settings import get_setting
from src.core.heatmap import build_heatmap_context
from src.reports.html_renderer import _build_env


def render_heatmap_print_html(conn, year_month=None, *, scope="full", outlier="inc"):
    """scope in {'full','matrix','lampiran'}; outlier in {'inc','exc'}."""
    month = (year_month or "").strip()
    if not month:
        month = get_setting(conn, "current_month", default="") or date.today().strftime("%Y-%m")
    ctx = build_heatmap_context(conn, month, exclude_outliers=(outlier == "exc"))
    env = _build_env()
    return env.get_template("heatmap_print.html.j2").render(scope=scope, **ctx)
