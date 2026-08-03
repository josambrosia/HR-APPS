"""Konteks + render HTML cetak untuk layar Rekap Dinas Paparan.

Server-free, mengikuti pola heatmap_print: fungsi mengembalikan STRING HTML;
pemanggil menulis ke temp file lalu membukanya di browser (Ctrl-P / Save PDF).
Konteksnya juga dipakai layar in-app supaya angka di layar & cetak identik.

v24.0.1: papan peringkat dipecah jadi dua (Dinas dan Paparan), masing-masing
dengan rentangnya sendiri; pegawai yang dikecualikan disaring di satu tempat
ini sehingga layar dan cetakan tak pernah berbeda.
"""
from datetime import datetime

from src.core.dinas_recap import rank_by, resolve_range, span_label
from src.core.week_utils import MONTH_NAMES_ID, full_month_range
from src.db.attendance import count_dinas_paparan_by_employee
from src.db.dinas_exclusions import list_excluded_ids
from src.db.settings import get_setting
from src.reports.html_renderer import _build_env
from src.reports.report_fonts import display_font_face_css

TEMPLATE_FILE = "dinas_recap_print.html.j2"


def _month_label(year_month: str) -> str:
    y, m = int(year_month[:4]), int(year_month[5:7])
    return f"{MONTH_NAMES_ID[m]} {y}"


def _rows_in_range(conn, year_month, span, excluded):
    start, end = resolve_range(year_month, span)
    rows = count_dinas_paparan_by_employee(conn, start, end)
    return [r for r in rows if r["employee_id"] not in excluded]


def build_dinas_recap_context(conn, year_month: str, span: str,
                              paparan_span: str = None) -> dict:
    """Konteks render untuk ketiga panel.

    Panel bulan selalu `year_month`. Papan Dinas memakai `span`; papan Paparan
    memakai `paparan_span` bila diberikan, selain itu mengikuti `span` (cetakan
    dan pemanggil lama tetap bekerja).
    """
    p_span = paparan_span or span
    excluded = list_excluded_ids(conn)

    m_start, m_end = full_month_range(year_month)
    month_rows = [r for r in count_dinas_paparan_by_employee(conn, m_start, m_end)
                  if r["employee_id"] not in excluded]
    month_totals = {
        "dinas": sum(r["dinas"] for r in month_rows),
        "paparan": sum(r["paparan"] for r in month_rows),
        "total": sum(r["total"] for r in month_rows),
    }

    dinas_rank = rank_by(_rows_in_range(conn, year_month, span, excluded), "dinas")
    paparan_rank = rank_by(_rows_in_range(conn, year_month, p_span, excluded), "paparan")

    def _champ(ranked):
        return ranked[0] if ranked and ranked[0]["value"] > 0 else None

    return {
        "month": year_month,
        "month_label": _month_label(year_month),
        "month_rows": month_rows,
        "month_totals": month_totals,
        "span": span,
        "span_label": span_label(year_month, span),
        "paparan_span": p_span,
        "paparan_span_label": span_label(year_month, p_span),
        "dinas_rank": dinas_rank,
        "paparan_rank": paparan_rank,
        "dinas_champion": _champ(dinas_rank),
        "paparan_champion": _champ(paparan_rank),
        "excluded_count": len(excluded),
        "generated_at": datetime.now().strftime("%d %b %Y"),
    }


def render_dinas_recap_html(conn, year_month: str, span: str,
                            paparan_span: str = None) -> str:
    """Render lembar cetak Rekap Dinas Paparan menjadi string HTML."""
    ctx = build_dinas_recap_context(conn, year_month, span, paparan_span)
    ctx["hr_officer_name"] = get_setting(conn, "hr_officer_name", default="")
    # Space Grotesk ditanam sebagai @font-face base64 — sama seperti laporan
    # per-pegawai, supaya PDF memakai typeface milik aplikasi, bukan fallback.
    ctx["font_face_css"] = display_font_face_css()
    return _build_env().get_template(TEMPLATE_FILE).render(**ctx)
