# tests/test_heatmap_print_render.py
import tempfile
import os
from pathlib import Path

from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.attendance import upsert_attendance
from src.reports.heatmap_print import render_heatmap_print_html


def _db():
    fd, p = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    p = Path(p)
    init_db(p)
    with get_connection(p) as conn:
        a = upsert_employee(conn, no_staff="1", nama="ANDI", dept="IT")
        upsert_attendance(conn, employee_id=a, tanggal="2026-05-04", hari="Senin",
                          tipe="Hari Kerja", jadwal="", masuk="09:15", keluar="16:30",
                          kerja_jam=None, lembur_jam=None, terlambat_menit=75,
                          has_issue=0, imported_from="W")
    return p


APPENDIX = "Lampiran — Detail Hari Kerja"


def test_full_has_matrix_and_appendix():
    with get_connection(_db()) as conn:
        html = render_heatmap_print_html(conn, "2026-05", scope="full", outlier="inc")
    assert "Mei 2026" in html and "ANDI" in html
    assert 'class="mx"' in html and APPENDIX in html


def test_matrix_only_omits_appendix():
    with get_connection(_db()) as conn:
        html = render_heatmap_print_html(conn, "2026-05", scope="matrix", outlier="inc")
    assert 'class="mx"' in html and APPENDIX not in html


def test_lampiran_only_omits_matrix():
    with get_connection(_db()) as conn:
        html = render_heatmap_print_html(conn, "2026-05", scope="lampiran", outlier="inc")
    assert APPENDIX in html and 'class="mx"' not in html
