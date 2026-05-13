"""Tests for list_recent_imports — distinct fingerprint files imported."""
import pytest
from src.db.connection import get_connection
from src.db.schema import init_db
from src.db.employees import upsert_employee
from src.db.attendance import upsert_attendance, list_recent_imports


@pytest.fixture
def db_with_imports(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    with get_connection(db_path) as conn:
        emp_id = upsert_employee(conn, no_staff="001", nama="Andika", dept="MKT")
        upsert_attendance(
            conn, employee_id=emp_id, tanggal="2026-04-01", hari="Rabu",
            tipe="Hari Kerja", jadwal="08-16",
            masuk="08:00", keluar="16:00",
            kerja_jam=8.0, lembur_jam=0.0, terlambat_menit=0, has_issue=0,
            imported_from="Fingerprint Mgg 1.xls",
        )
        emp_id2 = upsert_employee(conn, no_staff="002", nama="Bagus", dept="OPS")
        upsert_attendance(
            conn, employee_id=emp_id2, tanggal="2026-04-08", hari="Rabu",
            tipe="Hari Kerja", jadwal="08-16",
            masuk="08:00", keluar="16:00",
            kerja_jam=8.0, lembur_jam=0.0, terlambat_menit=0, has_issue=0,
            imported_from="Fingerprint Mgg 2.xls",
        )
    return db_path


def test_list_recent_imports_returns_distinct_files(db_with_imports):
    with get_connection(db_with_imports) as conn:
        rows = list_recent_imports(conn)
    files = [r["imported_from"] for r in rows]
    assert "Fingerprint Mgg 1.xls" in files
    assert "Fingerprint Mgg 2.xls" in files


def test_list_recent_imports_includes_emp_count(db_with_imports):
    with get_connection(db_with_imports) as conn:
        rows = list_recent_imports(conn)
    for r in rows:
        assert r["emp_count"] >= 1
        assert r["imported_at"] is not None


def test_list_recent_imports_respects_limit(db_with_imports):
    with get_connection(db_with_imports) as conn:
        rows = list_recent_imports(conn, limit=1)
    assert len(rows) == 1
