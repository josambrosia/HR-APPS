import sqlite3
from typing import Optional


def upsert_employee(
    conn: sqlite3.Connection,
    *,
    no_staff: str,
    nama: str,
    dept: Optional[str] = None,
    phone: Optional[str] = None,
) -> int:
    """Insert or update employee by no_staff, return id."""
    conn.execute(
        """
        INSERT INTO employees (no_staff, nama, dept, phone)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(no_staff) DO UPDATE SET
            nama = excluded.nama,
            dept = COALESCE(excluded.dept, employees.dept),
            phone = COALESCE(excluded.phone, employees.phone)
        """,
        (no_staff, nama, dept, phone),
    )
    row = conn.execute(
        "SELECT id FROM employees WHERE no_staff = ?", (no_staff,)
    ).fetchone()
    return row["id"]


def get_employee_by_no_staff(conn: sqlite3.Connection, no_staff: str):
    return conn.execute(
        "SELECT * FROM employees WHERE no_staff = ?", (no_staff,)
    ).fetchone()


def get_employee_by_nama(conn: sqlite3.Connection, nama: str):
    return conn.execute(
        "SELECT * FROM employees WHERE nama = ? COLLATE NOCASE", (nama,)
    ).fetchone()


def list_employees(conn: sqlite3.Connection, include_inactive: bool = False):
    if include_inactive:
        return conn.execute(
            "SELECT * FROM employees ORDER BY nama"
        ).fetchall()
    return conn.execute(
        "SELECT * FROM employees WHERE active = 1 ORDER BY nama"
    ).fetchall()
