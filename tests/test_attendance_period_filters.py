from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.attendance import (
    upsert_attendance, set_reason,
    list_issues_for_period, count_issues_for_period,
    count_summary_for_period,
)


def _seed_issues(conn):
    a = upsert_employee(conn, no_staff="1", nama="ANDIKA", dept="X")
    b = upsert_employee(conn, no_staff="2", nama="BUDI", dept="X")
    # ANDIKA: 2 issues (one resolved, one NA)
    upsert_attendance(conn, employee_id=a, tanggal="2026-04-09",
                      hari="Kamis", tipe="Hari Kerja", jadwal="08-16",
                      masuk=None, keluar=None, kerja_jam=None,
                      lembur_jam=None, terlambat_menit=None,
                      has_issue=1, imported_from="W2.xls")
    upsert_attendance(conn, employee_id=a, tanggal="2026-04-10",
                      hari="Jumat", tipe="Hari Kerja", jadwal="08-16",
                      masuk="08.10", keluar=None, kerja_jam=None,
                      lembur_jam=None, terlambat_menit=10,
                      has_issue=1, imported_from="W2.xls")
    # BUDI: 1 issue, open
    upsert_attendance(conn, employee_id=b, tanggal="2026-04-09",
                      hari="Kamis", tipe="Hari Kerja", jadwal="08-16",
                      masuk=None, keluar=None, kerja_jam=None,
                      lembur_jam=None, terlambat_menit=None,
                      has_issue=1, imported_from="W2.xls")
    # Set reasons
    rec = conn.execute(
        "SELECT id FROM attendance_records WHERE employee_id=? AND tanggal='2026-04-09'",
        (a,),
    ).fetchone()
    set_reason(conn, attendance_id=rec["id"], category="cuti", detail=None)
    rec2 = conn.execute(
        "SELECT id FROM attendance_records WHERE employee_id=? AND tanggal='2026-04-10'",
        (a,),
    ).fetchone()
    set_reason(conn, attendance_id=rec2["id"], category="na", detail=None)


def test_list_issues_sorted_by_nama_then_tanggal(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        _seed_issues(conn)
        rows = list_issues_for_period(conn, "2026-04-08", "2026-04-14")
    # ANDIKA, ANDIKA (sorted by tanggal), BUDI
    assert [r["nama"] for r in rows] == ["ANDIKA", "ANDIKA", "BUDI"]
    # within ANDIKA: 2026-04-09 before 2026-04-10
    assert rows[0]["tanggal"] == "2026-04-09"
    assert rows[1]["tanggal"] == "2026-04-10"


def test_list_issues_filter_resolved_false(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        _seed_issues(conn)
        open_only = list_issues_for_period(
            conn, "2026-04-08", "2026-04-14", resolved=False)
    # Only BUDI has no reason set
    assert len(open_only) == 1
    assert open_only[0]["nama"] == "BUDI"


def test_list_issues_filter_resolved_true(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        _seed_issues(conn)
        resolved = list_issues_for_period(
            conn, "2026-04-08", "2026-04-14", resolved=True)
    # ANDIKA has both resolved (cuti + na)
    names = [r["nama"] for r in resolved]
    assert names == ["ANDIKA", "ANDIKA"]


def test_count_issues_returns_breakdown(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        _seed_issues(conn)
        counts = count_issues_for_period(conn, "2026-04-08", "2026-04-14")
    assert counts == {"open": 1, "resolved": 1, "na": 1, "total": 3}


def test_count_summary_for_period_breakdown(temp_db_path):
    """Export-banner summary: distinct employees / issues / still-open issues."""
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        _seed_issues(conn)
        stats = count_summary_for_period(conn, "2026-04-08", "2026-04-14")
    # ANDIKA + BUDI; 3 has_issue rows; only BUDI's has no reason yet
    # ('na' counts as handled here — reason_category IS NOT NULL)
    assert stats == {"employees": 2, "issues": 3, "unresolved": 1}


def test_count_summary_for_period_empty_range_returns_zeros(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        _seed_issues(conn)
        stats = count_summary_for_period(conn, "2026-01-01", "2026-01-31")
    assert stats == {"employees": 0, "issues": 0, "unresolved": 0}
