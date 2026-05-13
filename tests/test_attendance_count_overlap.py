"""Tests for count_overlap — predict overwrite count before commit."""
import pytest
from src.db.connection import get_connection
from src.db.schema import init_db
from src.db.employees import upsert_employee
from src.db.attendance import upsert_attendance, count_overlap
from src.parsers.fingerprint import FingerprintRow


@pytest.fixture
def db_with_existing(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    with get_connection(db_path) as conn:
        emp_id = upsert_employee(conn, no_staff="001", nama="A", dept="X")
        upsert_attendance(
            conn, employee_id=emp_id, tanggal="2026-04-01", hari="Rabu",
            tipe="Hari Kerja", jadwal="08-16",
            masuk="08:00", keluar="16:00",
            kerja_jam=8.0, lembur_jam=0.0, terlambat_menit=0, has_issue=0,
            imported_from="seed.xls",
        )
    return db_path


def _make_row(no_staff, nama, dept, tanggal):
    """Build a FingerprintRow with minimum required fields."""
    return FingerprintRow(
        no_staff=no_staff, nama=nama, dept=dept,
        tanggal=tanggal, hari="Rabu",
        tipe="Hari Kerja", jadwal="08-16",
        masuk="08:00", keluar="16:00",
        kerja_jam=8.0, lembur_jam=0.0, terlambat_menit=0,
        source_file="test.xls",
    )


def test_count_overlap_all_new(db_with_existing):
    pending = [
        _make_row("002", "B", "X", "2026-04-08"),
        _make_row("003", "C", "X", "2026-04-09"),
    ]
    with get_connection(db_with_existing) as conn:
        result = count_overlap(conn, pending)
    assert result == {"new": 2, "overwrite": 0}


def test_count_overlap_all_overwrite(db_with_existing):
    pending = [
        _make_row("001", "A", "X", "2026-04-01"),  # exists
    ]
    with get_connection(db_with_existing) as conn:
        result = count_overlap(conn, pending)
    assert result == {"new": 0, "overwrite": 1}


def test_count_overlap_mixed(db_with_existing):
    pending = [
        _make_row("001", "A", "X", "2026-04-01"),  # overwrite
        _make_row("001", "A", "X", "2026-04-02"),  # new (emp exists, date doesn't)
        _make_row("002", "B", "X", "2026-04-01"),  # new (emp doesn't exist)
    ]
    with get_connection(db_with_existing) as conn:
        result = count_overlap(conn, pending)
    assert result == {"new": 2, "overwrite": 1}
