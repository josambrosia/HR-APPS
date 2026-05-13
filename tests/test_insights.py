from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.attendance import upsert_attendance, set_reason
from src.core.insights import (
    terlambat_ranking, top_n_terlambat, coaching_flag, karyawan_teladan,
    karyawan_teladan_top_n, ranking_departemen, hari_paling_rawan, resolution_rate,
    avg_minutes_per_late_event,
)


def _add_emp(conn, no, nama):
    return upsert_employee(conn, no_staff=no, nama=nama, dept="X")


def _add_att(conn, emp_id, tanggal, hari, masuk, keluar, terlambat, has_issue=0):
    upsert_attendance(
        conn, employee_id=emp_id, tanggal=tanggal, hari=hari,
        tipe="Hari Kerja", jadwal="08.00 - 16.00",
        masuk=masuk, keluar=keluar, kerja_jam=8.0,
        lembur_jam=None, terlambat_menit=terlambat,
        has_issue=has_issue, imported_from="W1.xls",
    )


def test_terlambat_excludes_work_justified_categories(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = _add_emp(conn, "1", "ANDI")
        # 100 mnt terlambat tapi alasan tugas_lapangan → tidak dihitung
        _add_att(conn, a, "2026-04-01", "Senin", "09.40", "16.00", 100)
        rec = conn.execute("SELECT id FROM attendance_records").fetchone()
        set_reason(conn, attendance_id=rec["id"], category="tugas_lapangan", detail="Sragen")

        b = _add_emp(conn, "2", "BUDI")
        _add_att(conn, b, "2026-04-01", "Senin", "08.50", "16.00", 50)  # personal late

        results = terlambat_ranking(conn, "2026-04-01", "2026-04-30")
        by_name = {r["nama"]: r["total_terlambat"] for r in results}
        assert by_name["ANDI"] == 0  # excluded
        assert by_name["BUDI"] == 50


def test_top_5_terlambat_returns_max_5_sorted_desc(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        for i, mins in enumerate([10, 50, 200, 30, 80, 5, 90], start=1):
            emp = _add_emp(conn, str(i), f"E{i}")
            _add_att(conn, emp, "2026-04-01", "Senin", "08.05", "16.00", mins)
        top = top_n_terlambat(conn, "2026-04-01", "2026-04-30", n=5)
        mins_list = [r["total_terlambat"] for r in top]
        assert mins_list == sorted(mins_list, reverse=True)
        assert len(top) == 5
        assert mins_list[0] == 200


def test_coaching_flag_includes_only_above_threshold(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = _add_emp(conn, "1", "OK")
        _add_att(conn, a, "2026-04-01", "Senin", "08.10", "16.00", 50)  # below 75
        b = _add_emp(conn, "2", "FLAGGED")
        _add_att(conn, b, "2026-04-01", "Senin", "08.50", "16.00", 80)
        b_id = b
        _add_att(conn, b_id, "2026-04-02", "Selasa", "08.10", "16.00", 10)  # total 90

        flagged = coaching_flag(conn, "2026-04-01", "2026-04-30", threshold=75)
        names = [r["nama"] for r in flagged]
        assert "FLAGGED" in names
        assert "OK" not in names


def test_karyawan_teladan_lowest_score_filter_min_3_days(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        # ANDI: 5 days, 0 mins late, no issues → score = 0
        andi = _add_emp(conn, "1", "ANDI")
        for d in range(1, 6):
            _add_att(conn, andi, f"2026-04-0{d}", "Hari", "08.00", "16.00", 0)
        # BUDI: 5 days, 30 mins late total
        budi = _add_emp(conn, "2", "BUDI")
        for d in range(1, 6):
            _add_att(conn, budi, f"2026-04-0{d}", "Hari", "08.06", "16.00", 6)
        # CIKO: only 2 days (filtered out by min hari_kerja=3)
        ciko = _add_emp(conn, "3", "CIKO")
        for d in range(1, 3):
            _add_att(conn, ciko, f"2026-04-0{d}", "Hari", "08.00", "16.00", 0)

        winner = karyawan_teladan(conn, "2026-04-01", "2026-04-30")
        assert winner is not None
        assert winner["nama"] == "ANDI"


def test_karyawan_teladan_top_n_returns_n_sorted_by_score(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        # 4 employees with increasing late minutes
        for i, late in enumerate([0, 5, 10, 20], start=1):
            emp = _add_emp(conn, str(i), f"E{i}")
            for d in range(1, 6):
                _add_att(conn, emp, f"2026-04-0{d}", "Hari",
                         "08.00" if late == 0 else f"08.{late:02d}",
                         "16.00", late)

        top3 = karyawan_teladan_top_n(conn, "2026-04-01", "2026-04-30", n=3)
        assert len(top3) == 3
        # Lowest score first
        assert top3[0]["nama"] == "E1"  # 0 late
        assert top3[1]["nama"] == "E2"  # 25 total late (5*5)
        assert top3[2]["nama"] == "E3"  # 50 total late


def test_karyawan_teladan_top_n_filter_min_3_days(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = _add_emp(conn, "1", "REGULAR")
        for d in range(1, 6):
            _add_att(conn, a, f"2026-04-0{d}", "Hari", "08.00", "16.00", 0)
        b = _add_emp(conn, "2", "SHORT")
        for d in range(1, 3):  # only 2 days
            _add_att(conn, b, f"2026-04-0{d}", "Hari", "08.00", "16.00", 0)
        top = karyawan_teladan_top_n(conn, "2026-04-01", "2026-04-30", n=10)
        names = [r["nama"] for r in top]
        assert "REGULAR" in names
        assert "SHORT" not in names


def test_ranking_departemen_sorted_by_terlambat(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        # Dept A: 100 min total, Dept B: 30 min total
        a1 = upsert_employee(conn, no_staff="A1", nama="A1", dept="DEPT_A")
        b1 = upsert_employee(conn, no_staff="B1", nama="B1", dept="DEPT_B")
        for d in range(1, 4):
            _add_att(conn, a1, f"2026-04-0{d}", "Hari", "08.30", "16.00", 30)
        for d in range(1, 4):
            _add_att(conn, b1, f"2026-04-0{d}", "Hari", "08.10", "16.00", 10)
        rows = ranking_departemen(conn, "2026-04-01", "2026-04-30")
        depts = [r["dept"] for r in rows]
        assert depts[0] == "DEPT_A"  # 90 min > 30 min
        assert depts[1] == "DEPT_B"


def test_hari_paling_rawan_sorted_by_terlambat(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        e = upsert_employee(conn, no_staff="1", nama="X", dept="A")
        # Senin: 1 late row; Selasa: 3 late rows
        _add_att(conn, e, "2026-04-01", "Selasa", "08.10", "16.00", 10)
        _add_att(conn, e, "2026-04-02", "Selasa", "08.20", "16.00", 20)
        _add_att(conn, e, "2026-04-03", "Selasa", "08.30", "16.00", 30)
        _add_att(conn, e, "2026-04-07", "Senin",  "08.05", "16.00", 5)
        rows = hari_paling_rawan(conn, "2026-04-01", "2026-04-30")
        # Selasa first (3 late rows), Senin second (1 late row)
        assert rows[0]["hari"] == "Selasa"
        assert rows[0]["terlambat_count"] == 3
        assert rows[1]["hari"] == "Senin"
        assert rows[1]["terlambat_count"] == 1


def test_resolution_rate_basic(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        e = upsert_employee(conn, no_staff="1", nama="X", dept="A")
        for d in range(1, 5):  # 4 issues
            _add_att(conn, e, f"2026-04-0{d}", "Hari", None, None, None, has_issue=1)
        # Resolve 2 of them
        ids = [r["id"] for r in conn.execute(
            "SELECT id FROM attendance_records ORDER BY id LIMIT 2"
        ).fetchall()]
        for i in ids:
            set_reason(conn, attendance_id=i, category="cuti", detail=None)
        result = resolution_rate(conn, "2026-04-01", "2026-04-30")
        assert result == {"resolved": 2, "total": 4, "rate_pct": 50.0}


def test_resolution_rate_empty(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        result = resolution_rate(conn, "2026-04-01", "2026-04-30")
        assert result == {"resolved": 0, "total": 0, "rate_pct": 0.0}


def test_terlambat_excludes_absent_days(temp_db_path):
    """Absent days (no masuk) must not contribute to terlambat_menit sums."""
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        emp = upsert_employee(conn, no_staff="1", nama="X", dept="A")
        # Day 1: present + late 30 min — should count
        _add_att(conn, emp, "2026-04-01", "Senin", "08.30", "16.00", 30)
        # Day 2: ABSENT (both null) but with bogus terlambat=99 — must NOT count
        upsert_attendance(
            conn, employee_id=emp, tanggal="2026-04-02",
            hari="Selasa", tipe="Hari Kerja", jadwal="08.00 - 16.00",
            masuk=None, keluar=None, kerja_jam=None,
            lembur_jam=None, terlambat_menit=99,
            has_issue=1, imported_from="W1.xls",
        )
        rows = terlambat_ranking(conn, "2026-04-01", "2026-04-30")
        r = rows[0]
        assert r["total_terlambat"] == 30  # NOT 30+99
        assert r["hari_telat"] == 1        # only day 1 counts
        assert r["tidak_hadir"] == 1       # day 2 counted as absent


def test_avg_minutes_per_late_event_empty(temp_db_path):
    """No late events -> returns 0.0"""
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        result = avg_minutes_per_late_event(conn, "2026-04-01", "2026-04-30")
        assert result == 0.0


def test_avg_minutes_per_late_event_single(temp_db_path):
    """One late event of 10 min -> returns 10.0"""
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = _add_emp(conn, "1", "A")
        _add_att(conn, a, "2026-04-13", "Senin", "08.10", "17.00", 10)
        result = avg_minutes_per_late_event(conn, "2026-04-01", "2026-04-30")
        assert result == 10.0


def test_avg_minutes_per_late_event_multi(temp_db_path):
    """Three events 10+20+30 across 2 emp -> avg 20.0"""
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = _add_emp(conn, "1", "A")
        b = _add_emp(conn, "2", "B")
        _add_att(conn, a, "2026-04-13", "Senin",  "08.10", "17.00", 10)
        _add_att(conn, a, "2026-04-14", "Selasa", "08.20", "17.00", 20)
        _add_att(conn, b, "2026-04-13", "Senin",  "08.30", "17.00", 30)
        result = avg_minutes_per_late_event(conn, "2026-04-01", "2026-04-30")
        assert result == 20.0


def test_avg_minutes_per_late_event_zero_excluded(temp_db_path):
    """terlambat_menit=0 (on time) not counted as an event"""
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = _add_emp(conn, "1", "A")
        b = _add_emp(conn, "2", "B")
        _add_att(conn, a, "2026-04-13", "Senin", "08.10", "17.00", 10)
        _add_att(conn, b, "2026-04-13", "Senin", "08.00", "17.00", 0)
        result = avg_minutes_per_late_event(conn, "2026-04-01", "2026-04-30")
        assert result == 10.0
