import os
import tempfile
from pathlib import Path

from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.wa_contacts import (
    mark_contacted, unmark_contacted, is_contacted, contacted_map,
)


def _db():
    fd, p = tempfile.mkstemp(suffix=".db"); os.close(fd); p = Path(p)
    init_db(p)
    return p


def test_schema_creates_wa_contacts():
    p = _db()
    with get_connection(p) as conn:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(wa_contacts)")}
    assert {"employee_id", "year_month", "contacted_at"} <= cols


def test_mark_and_is_contacted_is_month_scoped():
    p = _db()
    with get_connection(p) as conn:
        e = upsert_employee(conn, no_staff="1", nama="A", dept="X")
        assert is_contacted(conn, employee_id=e, year_month="2026-05") is False
        mark_contacted(conn, employee_id=e, year_month="2026-05")
        assert is_contacted(conn, employee_id=e, year_month="2026-05") is True
        assert is_contacted(conn, employee_id=e, year_month="2026-06") is False


def test_unmark():
    p = _db()
    with get_connection(p) as conn:
        e = upsert_employee(conn, no_staff="1", nama="A", dept="X")
        mark_contacted(conn, employee_id=e, year_month="2026-05")
        unmark_contacted(conn, employee_id=e, year_month="2026-05")
        assert is_contacted(conn, employee_id=e, year_month="2026-05") is False


def test_contacted_map_only_this_month():
    p = _db()
    with get_connection(p) as conn:
        e1 = upsert_employee(conn, no_staff="1", nama="A", dept="X")
        e2 = upsert_employee(conn, no_staff="2", nama="B", dept="X")
        mark_contacted(conn, employee_id=e1, year_month="2026-05")
        mark_contacted(conn, employee_id=e2, year_month="2026-06")
        assert list(contacted_map(conn, "2026-05").keys()) == [e1]


def test_mark_idempotent():
    p = _db()
    with get_connection(p) as conn:
        e = upsert_employee(conn, no_staff="1", nama="A", dept="X")
        mark_contacted(conn, employee_id=e, year_month="2026-05")
        mark_contacted(conn, employee_id=e, year_month="2026-05")
        assert is_contacted(conn, employee_id=e, year_month="2026-05")


def test_persists_across_connections():
    p = _db()
    with get_connection(p) as conn:
        e = upsert_employee(conn, no_staff="1", nama="A", dept="X")
        mark_contacted(conn, employee_id=e, year_month="2026-05")
    with get_connection(p) as conn:
        assert is_contacted(conn, employee_id=e, year_month="2026-05")
