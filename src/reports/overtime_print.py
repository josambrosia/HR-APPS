"""Konteks + render HTML cetak untuk layar Lembur (v26).

Server-free, mengikuti pola dinas_recap_print: fungsi mengembalikan STRING
HTML; pemanggil menulis ke temp file lalu membukanya di browser (Ctrl-P /
Save PDF). Dua mode: "all" (semua status) dan "accepted" (hanya Diterima,
memakai jam disetujui).
"""
from datetime import datetime

from src.core.overtime import format_duration, month_rows
from src.core.week_utils import MONTH_NAMES_ID, hari_name
from src.db.settings import get_setting
from src.reports.html_renderer import _build_env
from src.reports.report_fonts import display_font_face_css

TEMPLATE_FILE = "overtime.html.j2"

STATUS_LABELS = {
    "open": "Open",
    "diajukan": "Diajukan",
    "diterima": "Diterima",
    "tidak_diterima": "Tidak Diterima",
}


def _month_label(year_month: str) -> str:
    y, m = int(year_month[:4]), int(year_month[5:7])
    return f"{MONTH_NAMES_ID[m]} {y}"


def _tanggal_label(iso: str) -> str:
    try:
        y, m, d = iso.split("-")
        return f"{int(d)} {MONTH_NAMES_ID[int(m)]} {y}"
    except (ValueError, KeyError, IndexError):
        return iso


def build_overtime_context(conn, year_month: str, mode: str = "all") -> dict:
    rows = month_rows(conn, year_month)
    if mode == "accepted":
        rows = [r for r in rows if r.status == "diterima"]

    groups: list[dict] = []
    by_emp: dict[int, dict] = {}
    for r in rows:
        g = by_emp.get(r.employee_id)
        if g is None:
            g = {"nama": r.nama, "dept": r.dept, "rows": [],
                 "detected": 0, "approved": 0}
            by_emp[r.employee_id] = g
            groups.append(g)
        approved = r.approved_minutes if r.status == "diterima" else None
        g["rows"].append({
            "tanggal": _tanggal_label(r.tanggal),
            "hari": r.hari or hari_name(r.tanggal),
            "masuk": r.masuk or "—",
            "keluar": r.keluar or "—",
            "minutes": format_duration(r.minutes) if r.qualifies else "—",
            "approved": format_duration(approved) if approved is not None else "—",
            "status": STATUS_LABELS.get(r.status, r.status),
            "note": r.note or "",
            "holiday": r.is_holiday,
            "missing": r.missing_data,
        })
        g["detected"] += r.minutes
        if approved is not None:
            g["approved"] += approved

    for g in groups:
        g["days"] = len(g["rows"])
        g["detected_label"] = format_duration(g["detected"])
        g["approved_label"] = format_duration(g["approved"])

    grand_detected = sum(g["detected"] for g in groups)
    grand_approved = sum(g["approved"] for g in groups)

    return {
        "month": year_month,
        "month_label": _month_label(year_month),
        "mode": mode,
        "mode_label": ("Hanya Diterima" if mode == "accepted"
                       else "Semua Status"),
        "groups": groups,
        "employee_count": len(groups),
        "row_count": len(rows),
        "grand_detected": format_duration(grand_detected),
        "grand_approved": format_duration(grand_approved),
        "generated_at": datetime.now().strftime("%d %b %Y"),
    }


def render_overtime_print_html(conn, year_month: str, mode: str = "all") -> str:
    """Render lembar cetak Lembur menjadi string HTML."""
    ctx = build_overtime_context(conn, year_month, mode)
    ctx["hr_officer_name"] = get_setting(conn, "hr_officer_name", default="")
    ctx["font_face_css"] = display_font_face_css()
    return _build_env().get_template(TEMPLATE_FILE).render(**ctx)
