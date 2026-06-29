"""Render a one-employee monthly recap to an HTML string (browser → Ctrl-P).

Reuses build_heatmap_context (one employee slice) and the reports Jinja env so
paths resolve in dev and the PyInstaller bundle."""
from datetime import date

from src.db.settings import get_setting
from src.core.heatmap import build_heatmap_context
from src.reports.html_renderer import _build_env
from src.reports.report_fonts import display_font_face_css


def render_employee_report_html(conn, year_month, employee_id):
    month = (year_month or "").strip() or date.today().strftime("%Y-%m")
    ctx = build_heatmap_context(conn, month, exclude_outliers=False)
    emp = next((e for e in ctx["employees"] if e["employee_id"] == employee_id), None)
    if emp is None:
        emp = {"nama": "—", "dept": "", "employee_id": employee_id,
               "hk": 0, "summary": {}, "cells": {},
               "sorotan": {"hk": 0, "work_days": ctx["eff_hari_kerja"],
                           "pct_hadir": 0, "pct_color": "#737373",
                           "ontime_days": 0, "telat_total": 0, "telat_days": 0,
                           "dinas": 0, "sakit": 0}}
    no_staff = ""
    row = conn.execute("SELECT no_staff FROM employees WHERE id=?",
                       (employee_id,)).fetchone()
    if row and row[0]:
        no_staff = row[0]
    env = _build_env()
    return env.get_template("employee_report.html.j2").render(
        emp=emp,
        font_face_css=display_font_face_css(),
        no_staff=no_staff,
        month_label=ctx["month_label"],
        days=ctx["days"],
        weekday_of=ctx["weekday_of"],
        weekday_labels=ctx["weekday_labels"],
        weeks=ctx["weeks"],
        eff_hari_kerja=ctx["eff_hari_kerja"],
        legend=ctx["legend"],
        hr_officer_name=get_setting(conn, "hr_officer_name", default=""),
    )
