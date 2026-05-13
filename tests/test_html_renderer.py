from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.attendance import upsert_attendance
from src.reports.html_renderer import render_dashboard_html


def _add_emp(conn, no, nama, dept="X"):
    return upsert_employee(conn, no_staff=no, nama=nama, dept=dept)


def _add_att(conn, emp_id, tanggal, hari, masuk, keluar, terlambat, has_issue=0):
    upsert_attendance(
        conn, employee_id=emp_id, tanggal=tanggal, hari=hari,
        tipe="Hari Kerja", jadwal="08.00 - 16.00",
        masuk=masuk, keluar=keluar, kerja_jam=8.0,
        lembur_jam=None, terlambat_menit=terlambat,
        has_issue=has_issue, imported_from="W1.xls",
    )


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
    # New template content (single Light theme)
    assert "WEEKLY REPORT" in content
    assert "HR Absensi Dashboard" in content
    # KPI labels
    assert "Total Terlambat" in content
    assert "Rata-rata / Kejadian" in content
    assert "Coaching" in content
    assert "Teladan" in content
    # Section headings
    assert "Top 5 Paling Terlambat" in content
    assert "Karyawan Teladan" in content
    assert "Butuh Coaching" in content
    assert "Pola Jam Masuk" in content
    # Page 2: mandatory ranking
    assert "Ranking Lengkap" in content
    assert "Tidak Hadir" in content
    # Footer
    assert "[jts] josaphat tech solution" in content
    # Data sanity
    assert "ANDIKA" in content
    assert "50" in content  # terlambat menit shown


def test_ranking_is_mandatory_even_if_section_false(temp_db_path, tmp_path):
    """Ranking Lengkap renders even if sections.ranking=False (mandatory per spec)."""
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        emp = _add_emp(conn, "1", "XAVIER", dept="D")
        _add_att(conn, emp, "2026-04-13", "Senin", "08.00", "17.00", 0)
        out = render_dashboard_html(
            conn,
            period_start="2026-04-01", period_end="2026-04-30",
            period_label="APR 2026", out_dir=tmp_path,
            sections={
                "kpi": False, "top5_late": False, "top5_teladan": False,
                "coaching": False, "pola_jam_masuk": False, "ranking": False,
            },
        )
    html = out.read_text(encoding="utf-8")
    # Mandatory section heading is still there even when ranking=False
    assert "Ranking Lengkap" in html
    # Employee name still in ranking table even though caller asked to hide ranking
    assert "XAVIER" in html
    # Optional section headings respected (off). Note: "Pola Jam Masuk" still
    # appears as a CSS comment in <style> regardless, so we don't assert that here.
    assert "Top 5 Paling Terlambat" not in html
    assert "Karyawan Teladan" not in html
    assert "Butuh Coaching" not in html
