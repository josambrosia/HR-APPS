"""Tests for src/db/coaching.py — coaching session CRUD + list query."""
import sqlite3

from src.db.schema import DDL
from src.db.employees import upsert_employee
from src.db.attendance import upsert_attendance, set_reason
from src.db.coaching import (
    mark_coached, unmark_coached, get_coaching_notes,
    update_notes, list_coaching_for_week,
)


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(DDL)
    return conn


def _add_employee(conn, no_staff="E001", nama="ANDIKA", dept="ARGA DIRGA"):
    return upsert_employee(conn, no_staff=no_staff, nama=nama, dept=dept, phone=None)


def _add_late_attendance(conn, emp_id, tanggal, terlambat_menit):
    """Add a Hari Kerja attendance with masuk set (so terlambat counts)."""
    upsert_attendance(
        conn, employee_id=emp_id, tanggal=tanggal,
        hari="Senin", tipe="Hari Kerja", jadwal="08.00 - 16.00",
        masuk="08:15", keluar="16:00",
        kerja_jam=7.75, lembur_jam=0.0, terlambat_menit=terlambat_menit,
        has_issue=0, imported_from="test.xls",
    )


# ────────────────────────────────────────── CRUD


def test_mark_coached_inserts_row():
    conn = _conn()
    emp_id = _add_employee(conn)
    mark_coached(conn, employee_id=emp_id, week_start="2026-04-06")
    row = conn.execute(
        "SELECT * FROM coaching_sessions WHERE employee_id=? AND week_start=?",
        (emp_id, "2026-04-06"),
    ).fetchone()
    assert row is not None
    assert row["coached_at"] is not None
    assert row["notes"] is None


def test_mark_coached_idempotent_upserts_notes():
    conn = _conn()
    emp_id = _add_employee(conn)
    mark_coached(conn, employee_id=emp_id, week_start="2026-04-06", notes="first")
    mark_coached(conn, employee_id=emp_id, week_start="2026-04-06", notes="second")
    row = conn.execute(
        "SELECT notes FROM coaching_sessions WHERE employee_id=? AND week_start=?",
        (emp_id, "2026-04-06"),
    ).fetchone()
    assert row["notes"] == "second"
    # Still only one row
    count = conn.execute(
        "SELECT COUNT(*) c FROM coaching_sessions"
    ).fetchone()["c"]
    assert count == 1


def test_unmark_coached_deletes_row():
    conn = _conn()
    emp_id = _add_employee(conn)
    mark_coached(conn, employee_id=emp_id, week_start="2026-04-06")
    unmark_coached(conn, employee_id=emp_id, week_start="2026-04-06")
    row = conn.execute(
        "SELECT * FROM coaching_sessions WHERE employee_id=? AND week_start=?",
        (emp_id, "2026-04-06"),
    ).fetchone()
    assert row is None


def test_get_coaching_notes_returns_none_when_no_session():
    conn = _conn()
    emp_id = _add_employee(conn)
    result = get_coaching_notes(conn, employee_id=emp_id, week_start="2026-04-06")
    assert result is None


def test_update_notes_updates_existing_session():
    conn = _conn()
    emp_id = _add_employee(conn)
    mark_coached(conn, employee_id=emp_id, week_start="2026-04-06")
    update_notes(conn, employee_id=emp_id, week_start="2026-04-06", notes="discussed plan")
    result = get_coaching_notes(conn, employee_id=emp_id, week_start="2026-04-06")
    assert result == "discussed plan"


# ────────────────────────────────────────── list_coaching_for_week


def test_list_coaching_returns_over_threshold_pegawai():
    conn = _conn()
    emp1 = _add_employee(conn, no_staff="E001", nama="ANDIKA")
    emp2 = _add_employee(conn, no_staff="E002", nama="YASMIN")
    # ANDIKA: 80 mnt total (over 75)
    _add_late_attendance(conn, emp1, "2026-04-06", 50)
    _add_late_attendance(conn, emp1, "2026-04-07", 30)
    # YASMIN: 60 mnt total (under 75)
    _add_late_attendance(conn, emp2, "2026-04-06", 60)

    rows = [dict(r) for r in list_coaching_for_week(
        conn, week_start="2026-04-06", week_end="2026-04-12",
        threshold_minutes=75,
    )]
    assert len(rows) == 1
    assert rows[0]["nama"] == "ANDIKA"
    assert rows[0]["total_terlambat"] == 80
    assert rows[0]["is_coached"] == 0


def test_list_coaching_flags_is_coached_correctly():
    conn = _conn()
    emp_id = _add_employee(conn)
    _add_late_attendance(conn, emp_id, "2026-04-06", 100)
    mark_coached(conn, employee_id=emp_id, week_start="2026-04-06")

    rows = [dict(r) for r in list_coaching_for_week(
        conn, week_start="2026-04-06", week_end="2026-04-12",
        threshold_minutes=75,
    )]
    assert len(rows) == 1
    assert rows[0]["is_coached"] == 1
    assert rows[0]["coached_at"] is not None


def test_list_coaching_excludes_work_justified_lateness():
    conn = _conn()
    emp_id = _add_employee(conn)
    _add_late_attendance(conn, emp_id, "2026-04-06", 100)  # would be over threshold
    # But it's actually tugas_lapangan, so excluded
    row_id = conn.execute(
        "SELECT id FROM attendance_records WHERE tanggal='2026-04-06'"
    ).fetchone()["id"]
    set_reason(conn, attendance_id=row_id, category="tugas_lapangan",
               detail="kunjungan klien")

    rows = [dict(r) for r in list_coaching_for_week(
        conn, week_start="2026-04-06", week_end="2026-04-12",
        threshold_minutes=75,
    )]
    assert rows == []  # excluded — not over threshold once work-justified removed


def test_list_coaching_for_week_excludes_outlier(temp_db_path):
    """An employee excluded via the Outlier menu does not appear in the
    Coaching list, even when over the lateness threshold."""
    from src.db.schema import init_db
    from src.db.connection import get_connection
    from src.db.employees import upsert_employee
    from src.db.attendance import upsert_attendance
    from src.db.outlier import exclude_employee
    from src.db.coaching import list_coaching_for_week

    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = upsert_employee(conn, no_staff="1", nama="ANDI", dept="X")
        b = upsert_employee(conn, no_staff="2", nama="BUDI", dept="X")
        for emp in (a, b):
            upsert_attendance(
                conn, employee_id=emp, tanggal="2026-04-06", hari="Senin",
                tipe="Hari Kerja", jadwal="08.00 - 16.00",
                masuk="09.40", keluar="16.00", kerja_jam=6.0,
                lembur_jam=None, terlambat_menit=100, has_issue=0,
                imported_from="W1.xls",
            )
        exclude_employee(conn, a, "2026-04")  # ANDI excluded

        rows = list_coaching_for_week(
            conn, week_start="2026-04-06", week_end="2026-04-12",
            threshold_minutes=75,
        )
        names = [r["nama"] for r in rows]
        assert "ANDI" not in names
        assert "BUDI" in names


def test_list_coaching_for_week_excludes_holiday_dates():
    """Lateness on a holiday date does not push an employee over threshold."""
    from src.db.holidays import mark_holidays
    conn = _conn()
    emp = _add_employee(conn)
    # 50 min on a normal day + 50 min on a day that becomes a holiday
    _add_late_attendance(conn, emp, "2026-04-06", 50)
    _add_late_attendance(conn, emp, "2026-04-08", 50)
    # baseline: 100 total > 75 threshold -> employee appears
    base = list_coaching_for_week(
        conn, week_start="2026-04-06", week_end="2026-04-12", threshold_minutes=75,
    )
    assert len(base) == 1
    # mark April 8 holiday -> only 50 left -> below threshold -> not flagged
    mark_holidays(conn, ["2026-04-08"])
    after = list_coaching_for_week(
        conn, week_start="2026-04-06", week_end="2026-04-12", threshold_minutes=75,
    )
    assert after == []
