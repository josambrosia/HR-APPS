"""Tests for unresolve_issue — clears reason fields to revert to Open."""
import sqlite3

from src.db.schema import DDL
from src.db.employees import upsert_employee
from src.db.attendance import upsert_attendance, set_reason, unresolve_issue


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(DDL)
    return conn


def _add_resolved_issue(conn):
    """Create one employee with one resolved issue. Returns attendance_id."""
    emp_id = upsert_employee(conn, no_staff="E001", nama="ANDIKA",
                              dept="ARGA", phone=None)
    upsert_attendance(
        conn, employee_id=emp_id, tanggal="2026-04-01",
        hari="Rabu", tipe="Hari Kerja", jadwal="08.00 - 16.00",
        masuk=None, keluar=None,
        kerja_jam=None, lembur_jam=None, terlambat_menit=None,
        has_issue=1, imported_from="test.xls",
    )
    row_id = conn.execute(
        "SELECT id FROM attendance_records WHERE tanggal='2026-04-01'"
    ).fetchone()["id"]
    set_reason(conn, attendance_id=row_id,
               category="izin_sakit", detail=None)
    return row_id


def test_unresolve_clears_three_fields():
    conn = _conn()
    att_id = _add_resolved_issue(conn)
    unresolve_issue(conn, attendance_id=att_id)
    row = conn.execute(
        "SELECT reason_category, reason_detail, resolved_at "
        "FROM attendance_records WHERE id=?", (att_id,)
    ).fetchone()
    assert row["reason_category"] is None
    assert row["reason_detail"] is None
    assert row["resolved_at"] is None


def test_unresolve_does_not_touch_other_rows():
    conn = _conn()
    att_id_1 = _add_resolved_issue(conn)
    # Add a second resolved row
    upsert_attendance(
        conn, employee_id=1, tanggal="2026-04-02",
        hari="Kamis", tipe="Hari Kerja", jadwal="08.00 - 16.00",
        masuk=None, keluar=None,
        kerja_jam=None, lembur_jam=None, terlambat_menit=None,
        has_issue=1, imported_from="test.xls",
    )
    att_id_2 = conn.execute(
        "SELECT id FROM attendance_records WHERE tanggal='2026-04-02'"
    ).fetchone()["id"]
    set_reason(conn, attendance_id=att_id_2, category="cuti", detail=None)

    unresolve_issue(conn, attendance_id=att_id_1)

    row2 = conn.execute(
        "SELECT reason_category FROM attendance_records WHERE id=?", (att_id_2,)
    ).fetchone()
    assert row2["reason_category"] == "cuti"  # untouched


def test_unresolve_idempotent_on_already_null():
    conn = _conn()
    att_id = _add_resolved_issue(conn)
    unresolve_issue(conn, attendance_id=att_id)
    # Second call should no-op (fields already NULL)
    unresolve_issue(conn, attendance_id=att_id)
    row = conn.execute(
        "SELECT reason_category, reason_detail, resolved_at "
        "FROM attendance_records WHERE id=?", (att_id,)
    ).fetchone()
    assert row["reason_category"] is None
    assert row["reason_detail"] is None
    assert row["resolved_at"] is None
