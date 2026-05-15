"""Render dashboard HTML print output.

Produces a 2-page A4 HTML using the single "Light" theme template.
Page 1: Executive summary (KPI strip + Top 5 + Teladan + Coaching + Pola Jam Masuk).
Page 2: Ranking Lengkap (all employees with menit + kejadian + tidak hadir).
"""
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.config import DEFAULT_COACHING_THRESHOLD_MINUTES, BRAND_LOCKUP_LIGHT_SVG
from src.core.insights import (
    terlambat_ranking, top_n_terlambat, coaching_flag,
    avg_minutes_per_late_event, pola_jam_masuk,
)
from src.db.settings import get_setting

TEMPLATES_DIR = Path(__file__).parent / "templates"
TEMPLATE_FILE = "dashboard.html.j2"

DEFAULT_SECTIONS = {
    "kpi": True,
    "top5_late": True,
    "top5_teladan": True,
    "coaching": True,
    "pola_jam_masuk": True,
    "ranking": True,  # mandatory — always rendered regardless of toggle
}


def _build_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )


def _load_brand_lockup() -> str:
    """Return the JTS light-background lockup SVG markup, ready to inline into
    the print HTML. Strips the XML prolog (not valid mid-HTML-document).
    Falls back to a plain text wordmark if the asset is missing, so rendering
    never fails."""
    try:
        svg = BRAND_LOCKUP_LIGHT_SVG.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return "josaphat"
    if svg.lstrip().startswith("<?xml"):
        svg = svg.split("?>", 1)[1]
    return svg.strip()


def render_dashboard_html(
    conn: sqlite3.Connection,
    *,
    period_start: str,
    period_end: str,
    period_label: str,
    out_dir: Path,
    threshold: int = DEFAULT_COACHING_THRESHOLD_MINUTES,
    sections: Optional[dict] = None,
) -> Path:
    """Render the dashboard HTML print output and return its path.

    `sections` is a dict of booleans keyed by section name (see DEFAULT_SECTIONS).
    Missing keys default to True. The "ranking" section is always rendered even
    if set to False — it's mandatory per design spec.
    """
    if sections is None:
        sections = DEFAULT_SECTIONS.copy()
    else:
        sections = {**DEFAULT_SECTIONS, **sections}
    sections["ranking"] = True  # enforce mandatory

    ranking = terlambat_ranking(conn, period_start, period_end)
    top5_late = top_n_terlambat(conn, period_start, period_end, n=5)
    coaching = coaching_flag(conn, period_start, period_end, threshold=threshold)
    # Teladan = perfect attendance (no late, no absent). Derived from ranking
    # so KPI count and panel list always agree.
    teladan = [
        r for r in ranking
        if r['total_terlambat'] == 0 and r['hari_telat'] == 0 and r['absent_count'] == 0
    ]
    avg_min = avg_minutes_per_late_event(conn, period_start, period_end)
    jam_masuk = pola_jam_masuk(conn, period_start, period_end)

    # KPI tallies derived from ranking
    total_terlambat = sum(r['hari_telat'] for r in ranking)
    total_min = sum(r['total_terlambat'] for r in ranking)
    teladan_count = len(teladan)

    hr_officer_name = get_setting(conn, "hr_officer_name", default="")
    brand_lockup_svg = _load_brand_lockup()

    env = _build_env()
    tmpl = env.get_template(TEMPLATE_FILE)
    html = tmpl.render(
        period_label=period_label,
        period_start=period_start,
        period_end=period_end,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        kpi={
            "total_terlambat": total_terlambat,
            "total_min": total_min,
            "avg_min": avg_min,
            "coaching_count": len(coaching),
            "teladan_count": teladan_count,
        },
        top5_late=top5_late,
        teladan=teladan,
        coaching=coaching,
        coaching_threshold=threshold,
        jam_masuk=jam_masuk,
        ranking=ranking,
        sections=sections,
        hr_officer_name=hr_officer_name,
        brand_lockup_svg=brand_lockup_svg,
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_path = out_dir / f"hr-dashboard-{ts}.html"
    out_path.write_text(html, encoding="utf-8")
    return out_path
