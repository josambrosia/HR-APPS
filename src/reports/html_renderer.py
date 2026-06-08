"""Render dashboard HTML print output.

Produces a 2-page A4 HTML using the single "Light" theme template.
Page 1: Executive summary (KPI strip + Top 5 + Teladan + Coaching + Pola Jam Masuk).
Page 2: Ranking Lengkap (all employees with menit + kejadian + tidak hadir).
"""
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader

from src.config import BRAND_LOCKUP_LIGHT_SVG
from src.core.insights import (
    terlambat_ranking, top_n_terlambat, coaching_flag,
    avg_minutes_per_late_event, pola_jam_masuk, resolution_rate,
)
from src.db.outlier import list_active_exclusions
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
        autoescape=True,
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


def _previous_period(start: str, end: str, period_type: str) -> tuple[str, str]:
    """Compute (prev_start, prev_end) for the previous comparable period.

    Weekly: shift back by (end - start + 1) days.
    Monthly: previous calendar month, full range.
    """
    s = date.fromisoformat(start)
    e = date.fromisoformat(end)
    if period_type == "weekly":
        delta_days = (e - s).days + 1
        prev_e = s - timedelta(days=1)
        prev_s = prev_e - timedelta(days=delta_days - 1)
        return prev_s.isoformat(), prev_e.isoformat()
    # monthly
    if s.month == 1:
        prev_s = date(s.year - 1, 12, 1)
    else:
        prev_s = date(s.year, s.month - 1, 1)
    if prev_s.month == 12:
        prev_e = date(prev_s.year, 12, 31)
    else:
        prev_e = date(prev_s.year, prev_s.month + 1, 1) - timedelta(days=1)
    return prev_s.isoformat(), prev_e.isoformat()


def _kpi_delta(curr: int, prev: int, direction_good: str) -> dict:
    """Return {delta, arrow, color_class, period_word}.

    `direction_good` is "up" if a higher value is better, "down" if lower is better.
    Returns arrow="—" and delta=None when both periods are empty (zero).
    """
    if prev == 0 and curr == 0:
        return {"delta": None, "arrow": "—", "color_class": "neutral", "period_word": ""}
    delta = curr - prev
    if delta == 0:
        return {"delta": 0, "arrow": "→", "color_class": "neutral", "period_word": ""}
    if delta > 0:
        arrow = "▲"
        good = (direction_good == "up")
    else:
        arrow = "▼"
        good = (direction_good == "down")
    color_class = "good" if good else "bad"
    return {"delta": delta, "arrow": arrow, "color_class": color_class, "period_word": ""}


def render_dashboard_html(
    conn: sqlite3.Connection,
    *,
    period_start: str,
    period_end: str,
    period_label: str,
    out_dir: Path,
    threshold_info: Optional[dict] = None,
    sections: Optional[dict] = None,
    period_type: str = "monthly",
) -> Path:
    """Render the dashboard HTML print output and return its path.

    `sections` is a dict of booleans keyed by section name (see DEFAULT_SECTIONS).
    Missing keys default to True. The "ranking" section is always rendered even
    if set to False — it's mandatory per design spec.

    `threshold_info` is a dict {daily, working_days, effective} describing the
    dynamic coaching threshold for the period. `effective = daily * working_days`.
    When `working_days == 0`, the template renders a "no working-day data"
    fallback instead of the formula.
    """
    if sections is None:
        sections = DEFAULT_SECTIONS.copy()
    else:
        sections = {**DEFAULT_SECTIONS, **sections}
    sections["ranking"] = True  # enforce mandatory

    if threshold_info is None:
        threshold_info = {"daily": 15, "working_days": 0, "effective": 0}
    threshold_effective = threshold_info["effective"]

    ranking = terlambat_ranking(conn, period_start, period_end)
    top5_late = top_n_terlambat(conn, period_start, period_end, n=5)
    coaching = coaching_flag(conn, period_start, period_end, threshold=threshold_effective)
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

    # Previous-period KPI deltas
    prev_start, prev_end = _previous_period(period_start, period_end, period_type)
    prev_ranking = terlambat_ranking(conn, prev_start, prev_end)
    prev_coaching = coaching_flag(conn, prev_start, prev_end, threshold=threshold_effective)
    prev_teladan = [
        r for r in prev_ranking
        if r['total_terlambat'] == 0 and r['hari_telat'] == 0 and r['absent_count'] == 0
    ]
    prev_avg_min = avg_minutes_per_late_event(conn, prev_start, prev_end)
    prev_total_terlambat = sum(r['hari_telat'] for r in prev_ranking)

    period_word = "minggu lalu" if period_type == "weekly" else "bulan lalu"

    # Resolution rate strip (4d)
    res = resolution_rate(conn, period_start, period_end)
    res["open"] = res["total"] - res["resolved"]
    prev_res = resolution_rate(conn, prev_start, prev_end)
    if prev_res["total"] > 0:
        resolution_delta_pct = res["rate_pct"] - prev_res["rate_pct"]
        resolution_delta_arrow = "▲" if resolution_delta_pct > 0 else (
            "▼" if resolution_delta_pct < 0 else "→")
    else:
        resolution_delta_pct = None
        resolution_delta_arrow = "—"

    # Outlier transparency line (4e)
    active_outliers = list_active_exclusions(conn)
    outlier_names = ", ".join(o["nama"] for o in active_outliers)
    outlier_count = len(active_outliers)

    kpi_deltas = {
        "total_terlambat": _kpi_delta(total_terlambat, prev_total_terlambat, "down"),
        "avg_min":         _kpi_delta(int(avg_min), int(prev_avg_min), "down"),
        "coaching":        _kpi_delta(len(coaching), len(prev_coaching), "down"),
        "teladan":         _kpi_delta(teladan_count, len(prev_teladan), "up"),
    }
    for d in kpi_deltas.values():
        d["period_word"] = period_word

    hr_officer_name = get_setting(conn, "hr_officer_name", default="")
    brand_lockup_svg = _load_brand_lockup()

    period_badge_text = {
        "weekly": "WEEKLY REPORT",
        "monthly": "MONTHLY REPORT",
    }.get(period_type, "PERIOD REPORT")

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
        coaching_threshold_effective=threshold_info["effective"],
        coaching_threshold_daily=threshold_info["daily"],
        coaching_working_days=threshold_info["working_days"],
        jam_masuk=jam_masuk,
        ranking=ranking,
        sections=sections,
        kpi_deltas=kpi_deltas,
        hr_officer_name=hr_officer_name,
        brand_lockup_svg=brand_lockup_svg,
        period_badge_text=period_badge_text,
        resolution=res,
        resolution_delta_pct=resolution_delta_pct,
        resolution_delta_arrow=resolution_delta_arrow,
        outlier_count=outlier_count,
        outlier_names=outlier_names,
        period_word=period_word,
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_path = out_dir / f"hr-dashboard-{ts}.html"
    out_path.write_text(html, encoding="utf-8")
    return out_path
