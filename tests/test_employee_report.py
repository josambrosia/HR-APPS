import os
import tempfile
from pathlib import Path
from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.attendance import upsert_attendance
from src.db.settings import set_setting
from src.reports.employee_report import render_employee_report_html


def _seed():
    fd, p = tempfile.mkstemp(suffix=".db"); os.close(fd); p = Path(p)
    init_db(p)
    with get_connection(p) as conn:
        set_setting(conn, "hr_officer_name", "Budi Officer")
        e = upsert_employee(conn, no_staff="7", nama="ANDIKA WIJAYA", dept="ARGA DIRGA")
        upsert_attendance(conn, employee_id=e, tanggal="2026-05-04", hari="Senin",
                          tipe="Hari Kerja", jadwal="", masuk="08:30", keluar="16:30",
                          kerja_jam=None, lembur_jam=None, terlambat_menit=30,
                          has_issue=0, imported_from="W")
    return p, e


def test_report_has_identity_and_stats():
    p, e = _seed()
    with get_connection(p) as conn:
        html = render_employee_report_html(conn, "2026-05", e)
    assert "ANDIKA WIJAYA" in html
    assert "ARGA DIRGA" in html
    assert "Mei 2026" in html
    assert "Budi Officer" in html          # HR officer sign-off
    assert "Kehadiran" in html             # stats block label


def test_report_has_grid_and_perday_row():
    p, e = _seed()
    with get_connection(p) as conn:
        html = render_employee_report_html(conn, "2026-05", e)
    assert 'class="mx"' in html                 # mini-heatmap grid
    assert "Lampiran — Rincian Harian" in html  # per-day table heading
    assert "08:30" in html                      # the seeded punch appears
