import re
from datetime import datetime
from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.attendance import upsert_attendance
from src.reports.html_renderer import render_dashboard_html


def test_render_html_contains_key_sections(temp_db_path, tmp_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        emp = upsert_employee(conn, no_staff="1", nama="ANDIKA", dept="X")
        upsert_attendance(conn, employee_id=emp, tanggal="2026-04-01",
                          hari="Senin", tipe="Hari Kerja", jadwal="08.00 - 16.00",
                          masuk="08.50", keluar="16.00", kerja_jam=7.0,
                          lembur_jam=None, terlambat_menit=50,
                          has_issue=0, imported_from="W1.xls")
        out = render_dashboard_html(
            conn, period_start="2026-04-01", period_end="2026-04-30",
            period_label="April 2026", out_dir=tmp_path,
        )
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert "Dashboard Insights" in content
    assert "ANDIKA" in content
    assert "50" in content  # terlambat menit shown
    assert "Top 5 Paling Terlambat" in content
    assert "Ranking Lengkap" in content
