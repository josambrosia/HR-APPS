import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.config import DEFAULT_COACHING_THRESHOLD_MINUTES
from src.core.insights import (
    terlambat_ranking, top_n_terlambat, coaching_flag, karyawan_teladan_top_n,
    ranking_departemen, hari_paling_rawan,
)

TEMPLATES_DIR = Path(__file__).parent / "templates"

TEMPLATE_NAMES = {
    "default":     "dashboard.html.j2",
    "editorial":   "dashboard_v1_editorial.html.j2",
    "dark_glass":  "dashboard_v2_dark_glass.html.j2",
    "infographic": "dashboard_v3_infographic.html.j2",
    "corporate":   "dashboard_v4_corporate.html.j2",
}

DEFAULT_SECTIONS = {
    "kpi": True, "top5_late": True, "top5_teladan": True,
    "coaching": True, "departemen": True, "hari_rawan": True, "ranking": True,
}


def _build_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )


def render_dashboard_html(
    conn: sqlite3.Connection,
    *,
    period_start: str,
    period_end: str,
    period_label: str,
    out_dir: Path,
    threshold: int = DEFAULT_COACHING_THRESHOLD_MINUTES,
    template_name: str = "default",
    sections: Optional[dict] = None,
) -> Path:
    """Render dashboard HTML and write to out_dir. Returns the file path.

    template_name picks the theme; sections is a dict of booleans deciding
    which content blocks to include.
    """
    if sections is None:
        sections = DEFAULT_SECTIONS.copy()
    tmpl_file = TEMPLATE_NAMES.get(template_name, TEMPLATE_NAMES["default"])

    ranking = terlambat_ranking(conn, period_start, period_end)
    top5_late = top_n_terlambat(conn, period_start, period_end, n=5)
    coaching = coaching_flag(conn, period_start, period_end, threshold=threshold)
    top5_teladan = karyawan_teladan_top_n(conn, period_start, period_end, n=5)
    dept_rows = ranking_departemen(conn, period_start, period_end)
    day_rows = hari_paling_rawan(conn, period_start, period_end)

    total_terlambat = sum(r["total_terlambat"] for r in ranking)
    total_absen = conn.execute(
        """
        SELECT COUNT(*) FROM attendance_records
         WHERE tanggal BETWEEN ? AND ?
           AND tipe = 'Hari Kerja' AND masuk IS NULL AND keluar IS NULL
        """,
        (period_start, period_end),
    ).fetchone()[0]

    env = _build_env()
    tmpl = env.get_template(tmpl_file)
    html = tmpl.render(
        period_label=period_label,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        kpi={
            "total_terlambat": total_terlambat,
            "total_absen": total_absen,
            "coaching_count": len(coaching),
        },
        top5_late=top5_late,
        top5_teladan=top5_teladan,
        coaching=coaching,
        coaching_threshold=threshold,
        ranking=ranking,
        ranking_departemen=dept_rows,
        hari_paling_rawan=day_rows,
        sections=sections,
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_path = out_dir / f"hr-dashboard-{ts}.html"
    out_path.write_text(html, encoding="utf-8")
    return out_path
