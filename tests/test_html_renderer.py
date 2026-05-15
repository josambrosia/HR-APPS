from pathlib import Path

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
    # Footer — brand lockup (inlined SVG) + "Tech Solution" line
    assert "<svg" in content
    assert "Tech Solution" in content
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


def test_render_html_includes_hr_officer_signoff(temp_db_path, tmp_path):
    """The print includes an HR Officer in Charge sign-off with the saved name."""
    from src.db.settings import set_setting
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        set_setting(conn, "hr_officer_name", "Supriyadi, S.E.")
        emp = _add_emp(conn, "1", "ANDI")
        _add_att(conn, emp, "2026-04-01", "Senin", "08.00", "16.00", 0)
        out = render_dashboard_html(
            conn, period_start="2026-04-01", period_end="2026-04-30",
            period_label="April 2026", out_dir=tmp_path,
        )
    content = out.read_text(encoding="utf-8")
    assert "HR Officer in Charge" in content
    assert "Supriyadi, S.E." in content


def test_render_html_signoff_renders_when_name_empty(temp_db_path, tmp_path):
    """The sign-off block + label render even when no HR name is set."""
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        emp = _add_emp(conn, "1", "ANDI")
        _add_att(conn, emp, "2026-04-01", "Senin", "08.00", "16.00", 0)
        out = render_dashboard_html(
            conn, period_start="2026-04-01", period_end="2026-04-30",
            period_label="April 2026", out_dir=tmp_path,
        )
    content = out.read_text(encoding="utf-8")
    assert "HR Officer in Charge" in content


def test_render_html_inlines_brand_lockup_svg(temp_db_path, tmp_path):
    """The JTS lockup is inlined as <svg>, not referenced as an external file,
    and the old plain-text footer is gone."""
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        emp = _add_emp(conn, "1", "ANDI")
        _add_att(conn, emp, "2026-04-01", "Senin", "08.00", "16.00", 0)
        out = render_dashboard_html(
            conn, period_start="2026-04-01", period_end="2026-04-30",
            period_label="April 2026", out_dir=tmp_path,
        )
    content = out.read_text(encoding="utf-8")
    assert "<svg" in content                              # lockup inlined as SVG
    assert "josaphat" in content                          # the lockup wordmark text
    assert "[jts] josaphat tech solution" not in content  # old text footer removed


def test_load_brand_lockup_falls_back_to_text_when_svg_missing(monkeypatch):
    """_load_brand_lockup returns 'josaphat' when the asset file is absent."""
    import src.reports.html_renderer as mod
    monkeypatch.setattr(mod, "BRAND_LOCKUP_LIGHT_SVG", Path("/nonexistent/lockup.svg"))
    assert mod._load_brand_lockup() == "josaphat"


def test_render_html_page_margin_zero(temp_db_path, tmp_path):
    """@page margin is 0 (suppresses the browser's auto path/header/footer);
    the page inset moves into .doc padding."""
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        emp = _add_emp(conn, "1", "ANDI")
        _add_att(conn, emp, "2026-04-01", "Senin", "08.00", "16.00", 0)
        out = render_dashboard_html(
            conn, period_start="2026-04-01", period_end="2026-04-30",
            period_label="April 2026", out_dir=tmp_path,
        )
    content = out.read_text(encoding="utf-8")
    assert "@page{size:A4;margin:0}" in content
    assert ".doc{padding:14mm}" in content


def test_render_html_escapes_hr_officer_name(temp_db_path, tmp_path):
    """hr_officer_name is user input — it must be HTML-escaped in the print
    output, not injected as raw markup."""
    from src.db.settings import set_setting
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        set_setting(conn, "hr_officer_name", "<script>alert(1)</script>")
        emp = _add_emp(conn, "1", "ANDI")
        _add_att(conn, emp, "2026-04-01", "Senin", "08.00", "16.00", 0)
        out = render_dashboard_html(
            conn, period_start="2026-04-01", period_end="2026-04-30",
            period_label="April 2026", out_dir=tmp_path,
        )
    content = out.read_text(encoding="utf-8")
    assert "<script>alert(1)</script>" not in content
    assert "&lt;script&gt;" in content


def test_render_html_print_footer_in_tfoot(temp_db_path, tmp_path):
    """The footer lives inside <tfoot> so browsers natively repeat it at the
    bottom of every printed page (the reliable cross-browser pattern;
    position:fixed in @media print was unreliable in Chrome's print engine
    and the footer disappeared entirely on multi-page PDFs)."""
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        emp = _add_emp(conn, "1", "ANDI")
        _add_att(conn, emp, "2026-04-01", "Senin", "08.00", "16.00", 0)
        out = render_dashboard_html(
            conn, period_start="2026-04-01", period_end="2026-04-30",
            period_label="April 2026", out_dir=tmp_path,
        )
    content = out.read_text(encoding="utf-8")
    # Exactly one .print-footer block
    assert content.count('class="print-footer"') == 1
    # And it lives inside <tfoot> for per-page repeat
    assert "<tfoot>" in content
    tfoot_start = content.find("<tfoot>")
    tfoot_end = content.find("</tfoot>", tfoot_start)
    assert tfoot_start != -1 and tfoot_end != -1
    assert 'class="print-footer"' in content[tfoot_start:tfoot_end], \
        "expected the .print-footer block to live inside <tfoot>"


def test_render_html_no_legacy_b_footer(temp_db_path, tmp_path):
    """The old paired .b-footer markup is fully removed."""
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        emp = _add_emp(conn, "1", "ANDI")
        _add_att(conn, emp, "2026-04-01", "Senin", "08.00", "16.00", 0)
        out = render_dashboard_html(
            conn, period_start="2026-04-01", period_end="2026-04-30",
            period_label="April 2026", out_dir=tmp_path,
        )
    content = out.read_text(encoding="utf-8")
    assert 'class="b-footer"' not in content
    # No more hardcoded per-page numbering
    assert "page 1/2" not in content
    assert "page 2/2" not in content
