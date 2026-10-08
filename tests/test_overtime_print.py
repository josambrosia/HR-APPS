from src.db.attendance import upsert_attendance
from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.overtime import apply_status
from src.db.schema import init_db
from src.db.settings import set_setting
from src.reports.overtime_print import (build_overtime_context,
                                        render_overtime_print_html)


def _seed(conn):
    a = upsert_employee(conn, no_staff="1", nama="Agus", dept="Ops")
    b = upsert_employee(conn, no_staff="2", nama="Budi", dept="Gudang")

    def att(eid, tanggal, masuk, keluar):
        upsert_attendance(
            conn, employee_id=eid, tanggal=tanggal, hari=None,
            tipe="Hari Kerja", jadwal=None, masuk=masuk, keluar=keluar,
            kerja_jam=None, lembur_jam=None, terlambat_menit=0,
            has_issue=0, imported_from="t")

    att(a, "2026-10-01", "09:00", "19:30")   # 150 open
    att(a, "2026-10-04", "09:00", "14:00")   # 300 (Minggu)
    att(b, "2026-10-02", "09:00", "19:00")   # 120
    apply_status(conn, employee_id=a, tanggal="2026-10-04",
                 status="diterima", detected_minutes=300, approved_minutes=300)
    apply_status(conn, employee_id=b, tanggal="2026-10-02",
                 status="tidak_diterima", detected_minutes=120)
    return a, b


def test_context_all_statuses(tmp_path):
    p = tmp_path / "o.db"
    init_db(p)
    with get_connection(p) as conn:
        _seed(conn)
        ctx = build_overtime_context(conn, "2026-10", mode="all")
    assert ctx["row_count"] == 3
    assert ctx["employee_count"] == 2
    assert ctx["grand_detected"] == "9j 30m"
    assert ctx["grand_approved"] == "5j"
    statuses = [r["status"] for g in ctx["groups"] for r in g["rows"]]
    assert sorted(statuses) == ["Diterima", "Open", "Tidak Diterima"]


def test_context_accepted_only(tmp_path):
    p = tmp_path / "o.db"
    init_db(p)
    with get_connection(p) as conn:
        _seed(conn)
        ctx = build_overtime_context(conn, "2026-10", mode="accepted")
    assert ctx["row_count"] == 1
    assert ctx["employee_count"] == 1
    assert ctx["groups"][0]["nama"] == "Agus"
    assert ctx["groups"][0]["rows"][0]["status"] == "Diterima"
    assert ctx["grand_approved"] == "5j"


def test_render_html_smoke(tmp_path):
    p = tmp_path / "o.db"
    init_db(p)
    with get_connection(p) as conn:
        _seed(conn)
        set_setting(conn, "hr_officer_name", "Budi HR")
        html = render_overtime_print_html(conn, "2026-10", mode="all")
    assert "Agus" in html and "Budi" in html
    assert "Budi HR" in html
    assert "Rekap Lembur" in html
    assert "Semua Status" in html


def test_render_html_accepted_mode_label(tmp_path):
    p = tmp_path / "o.db"
    init_db(p)
    with get_connection(p) as conn:
        _seed(conn)
        html = render_overtime_print_html(conn, "2026-10", mode="accepted")
    assert "Hanya Diterima" in html
    assert "Tidak Diterima" not in html


def test_print_includes_orphan_decision(tmp_path):
    """Keputusan tanpa baris absensi tetap tercetak + diberi keterangan."""
    from src.db.attendance import delete_attendance
    p = tmp_path / "o.db"
    init_db(p)
    with get_connection(p) as conn:
        a, _b = _seed(conn)
        apply_status(conn, employee_id=a, tanggal="2026-10-01",
                     status="diajukan", detected_minutes=150)
        delete_attendance(conn, employee_id=a, tanggal="2026-10-01")
        ctx = build_overtime_context(conn, "2026-10", mode="all")
        html = render_overtime_print_html(conn, "2026-10", mode="all")
    assert "data absensi tidak ditemukan" in html
    statuses = [r["status"] for g in ctx["groups"] for r in g["rows"]]
    assert "Diajukan" in statuses


def test_status_dot_markers_in_print(tmp_path):
    """Semua status tampil dengan titik warna (opsi C), Diajukan biru."""
    from src.db.overtime import apply_status
    p = tmp_path / "o.db"
    init_db(p)
    with get_connection(p) as conn:
        _seed(conn)
        b = conn.execute(
            "SELECT id FROM employees WHERE no_staff = '2'").fetchone()["id"]
        upsert_attendance(
            conn, employee_id=b, tanggal="2026-10-05", hari=None,
            tipe="Hari Kerja", jadwal=None, masuk="09:00", keluar="19:00",
            kerja_jam=None, lembur_jam=None, terlambat_menit=0,
            has_issue=0, imported_from="t")
        apply_status(conn, employee_id=b, tanggal="2026-10-05",
                     status="diajukan", detected_minutes=120)
        html = render_overtime_print_html(conn, "2026-10", mode="all")
    for marker in ('class="st open"', 'class="st diajukan"',
                   'class="st diterima"', 'class="st tidak_diterima"'):
        assert marker in html, f"status {marker} tidak ada"
    assert "border-radius:50%" in html
    assert ".st.diajukan::before{background:#3B82F6}" in html
    assert ".st.open::before{background:#F59E0B}" in html
    assert ".st.diterima::before{background:#10B981}" in html
    assert ".st.tidak_diterima::before{background:#EF4444}" in html
