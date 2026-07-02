from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.employees import (
    upsert_employee, get_employee_by_no_staff, get_employee_by_id, list_employees,
    toggle_employee_active,
)


def test_upsert_creates_new(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        emp_id = upsert_employee(conn, no_staff="9001", nama="BUDI", dept="TEST")
        assert emp_id > 0


def test_upsert_updates_existing(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        id1 = upsert_employee(conn, no_staff="9001", nama="BUDI", dept="TEST")
        id2 = upsert_employee(conn, no_staff="9001", nama="BUDI ARGA", dept="OPS")
        assert id1 == id2
        emp = get_employee_by_no_staff(conn, "9001")
        assert emp["nama"] == "BUDI ARGA"
        assert emp["dept"] == "OPS"


def test_list_employees_returns_only_active(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        upsert_employee(conn, no_staff="9001", nama="BUDI", dept="TEST")
        upsert_employee(conn, no_staff="9002", nama="ANI", dept="TEST")
        conn.execute("UPDATE employees SET active=0 WHERE no_staff='9002'")
        rows = list_employees(conn)
        names = [r["nama"] for r in rows]
        assert "BUDI" in names
        assert "ANI" not in names


def test_list_employees_include_inactive(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        upsert_employee(conn, no_staff="9001", nama="BUDI", dept="TEST")
        upsert_employee(conn, no_staff="9002", nama="ANI", dept="TEST")
        conn.execute("UPDATE employees SET active=0 WHERE no_staff='9002'")
        rows = list_employees(conn, include_inactive=True)
        assert len(rows) == 2


def test_get_employee_by_id_returns_row(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        eid = upsert_employee(conn, no_staff="9001", nama="BUDI",
                              dept="TEST", phone="081234567890")
        emp = get_employee_by_id(conn, eid)
        assert emp["nama"] == "BUDI"
        assert emp["dept"] == "TEST"
        assert emp["phone"] == "081234567890"


def test_get_employee_by_id_unknown_returns_none(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        assert get_employee_by_id(conn, 99999) is None


def test_toggle_employee_active_flips_both_ways(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        emp_id = upsert_employee(conn, no_staff="9001", nama="BUDI", dept="TEST")
        assert get_employee_by_no_staff(conn, "9001")["active"] == 1
        toggle_employee_active(conn, emp_id)
        assert get_employee_by_no_staff(conn, "9001")["active"] == 0
        toggle_employee_active(conn, emp_id)
        assert get_employee_by_no_staff(conn, "9001")["active"] == 1


def test_toggle_employee_active_only_touches_target(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        budi = upsert_employee(conn, no_staff="9001", nama="BUDI", dept="TEST")
        upsert_employee(conn, no_staff="9002", nama="ANI", dept="TEST")
        toggle_employee_active(conn, budi)
        assert get_employee_by_no_staff(conn, "9001")["active"] == 0
        assert get_employee_by_no_staff(conn, "9002")["active"] == 1
