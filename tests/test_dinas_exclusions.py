"""Pengecualian pegawai khusus layar Rekap Dinas Paparan."""
import pytest

from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.dinas_exclusions import (
    list_excluded_ids, set_excluded_ids, list_employees_with_exclusion)


@pytest.fixture
def db(tmp_path):
    p = tmp_path / "hr.db"
    init_db(p)
    with get_connection(p) as conn:
        a = upsert_employee(conn, no_staff="S1", nama="Andi", dept="Ops")
        b = upsert_employee(conn, no_staff="S2", nama="Budi", dept="Sales")
        c = upsert_employee(conn, no_staff="S3", nama="Cici", dept="HR")
    return p, a, b, c


def test_empty_by_default(db):
    p, *_ = db
    with get_connection(p) as conn:
        assert list_excluded_ids(conn) == set()


def test_set_and_read_back(db):
    p, a, b, _c = db
    with get_connection(p) as conn:
        set_excluded_ids(conn, [a, b])
    with get_connection(p) as conn:
        assert list_excluded_ids(conn) == {a, b}


def test_set_replaces_whole_list(db):
    p, a, b, c = db
    with get_connection(p) as conn:
        set_excluded_ids(conn, [a, b])
        set_excluded_ids(conn, [c])
        assert list_excluded_ids(conn) == {c}


def test_set_empty_clears(db):
    p, a, _b, _c = db
    with get_connection(p) as conn:
        set_excluded_ids(conn, [a])
        set_excluded_ids(conn, [])
        assert list_excluded_ids(conn) == set()


def test_set_is_idempotent(db):
    p, a, _b, _c = db
    with get_connection(p) as conn:
        set_excluded_ids(conn, [a, a, a])
        assert list_excluded_ids(conn) == {a}


def test_listing_marks_excluded_and_sorts_by_name(db):
    p, a, _b, _c = db
    with get_connection(p) as conn:
        set_excluded_ids(conn, [a])
        rows = list_employees_with_exclusion(conn)
    assert [r["nama"] for r in rows] == ["Andi", "Budi", "Cici"]
    assert rows[0]["excluded"] is True
    assert rows[1]["excluded"] is False


def test_listing_skips_inactive_employees(db):
    p, _a, _b, _c = db
    with get_connection(p) as conn:
        conn.execute("UPDATE employees SET active = 0 WHERE nama = 'Cici'")
        rows = list_employees_with_exclusion(conn)
    assert "Cici" not in {r["nama"] for r in rows}


def test_deleting_employee_drops_exclusion(db):
    """ON DELETE CASCADE menjaga tabel tidak menyimpan id hantu."""
    p, a, _b, _c = db
    with get_connection(p) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        set_excluded_ids(conn, [a])
        conn.execute("DELETE FROM employees WHERE id = ?", (a,))
        assert list_excluded_ids(conn) == set()
