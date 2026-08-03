"""Konteks + render HTML cetak untuk layar Rekap Dinas.

Server-free, mengikuti pola heatmap_print: fungsi mengembalikan STRING HTML;
pemanggil menulis ke temp file lalu membukanya di browser (Ctrl-P / Save PDF).
Konteksnya juga dipakai layar in-app supaya angka di layar & cetak identik.
"""
from datetime import datetime

from src.core.dinas_recap import (
    champion_of, decorate_ranks, resolve_range, span_label)
from src.core.week_utils import MONTH_NAMES_ID, full_month_range
from src.db.attendance import count_dinas_paparan_by_employee
from src.db.settings import get_setting
from src.reports.html_renderer import _build_env
from src.reports.report_fonts import display_font_face_css

TEMPLATE_FILE = "dinas_recap_print.html.j2"


def _month_label(year_month: str) -> str:
    y, m = int(year_month[:4]), int(year_month[5:7])
    return f"{MONTH_NAMES_ID[m]} {y}"


def build_dinas_recap_context(conn, year_month: str, span: str) -> dict:
    """Konteks render untuk kedua panel.

    Panel kiri selalu bulan `year_month`; panel kanan mengikuti `span`.
    Baris peringkat dilengkapi rank, mark (👑/💎), dan persentase bar:
      bar_pct      — panjang bar relatif terhadap pemuncak
      dinas_pct    — porsi dinas DI DALAM bar (dinas+paparan = 100)
      paparan_pct  — sisanya
    """
    m_start, m_end = full_month_range(year_month)
    month_rows = count_dinas_paparan_by_employee(conn, m_start, m_end)
    month_totals = {
        "dinas": sum(r["dinas"] for r in month_rows),
        "paparan": sum(r["paparan"] for r in month_rows),
        "total": sum(r["total"] for r in month_rows),
    }

    r_start, r_end = resolve_range(year_month, span)
    rank_rows = decorate_ranks(count_dinas_paparan_by_employee(conn, r_start, r_end))
    champion = champion_of(rank_rows)

    return {
        "month": year_month,
        "month_label": _month_label(year_month),
        "month_rows": month_rows,
        "month_totals": month_totals,
        "span": span,
        "span_label": span_label(year_month, span),
        "rank_rows": rank_rows,
        "champion": champion,
        "generated_at": datetime.now().strftime("%d %b %Y"),
    }


def render_dinas_recap_html(conn, year_month: str, span: str) -> str:
    """Render lembar cetak Rekap Dinas menjadi string HTML."""
    ctx = build_dinas_recap_context(conn, year_month, span)
    ctx["hr_officer_name"] = get_setting(conn, "hr_officer_name", default="")
    # Space Grotesk ditanam sebagai @font-face base64 — sama seperti laporan
    # per-pegawai, supaya PDF memakai typeface milik aplikasi, bukan fallback.
    ctx["font_face_css"] = display_font_face_css()
    return _build_env().get_template(TEMPLATE_FILE).render(**ctx)
