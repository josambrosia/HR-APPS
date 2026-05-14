"""Data access for the Outlier / Pengecualian feature.

An employee is "excluded" from analytics for a given analysis-month M when
there is an outlier_exclusions row where:
    effective_from <= M AND (effective_until IS NULL OR M < effective_until)

Months are "YYYY-MM" strings; string comparison works because the format
is zero-padded and lexicographic order matches chronological order.
"""
import sqlite3
from datetime import datetime, UTC
from typing import List


def excluded_employee_ids(conn: sqlite3.Connection, year_month: str) -> set:
    """Set of employee_id excluded from analytics for the given month.

    `year_month` is "YYYY-MM". Used by the insights layer and the Coaching
    data layer to drop Outlier employees from aggregations.
    """
    rows = conn.execute(
        """
        SELECT DISTINCT employee_id
          FROM outlier_exclusions
         WHERE effective_from <= ?
           AND (effective_until IS NULL OR ? < effective_until)
        """,
        (year_month, year_month),
    ).fetchall()
    return {r[0] for r in rows}


def exclusion_sql(excluded: set, column: str = "employee_id") -> tuple:
    """Build an ' AND <column> NOT IN (?,?,...)' SQL fragment + params tuple.

    Returns ('', ()) when `excluded` is empty so callers can splice it in
    unconditionally without producing invalid `NOT IN ()` SQL.
    """
    if not excluded:
        return "", ()
    placeholders = ",".join("?" for _ in excluded)
    return f" AND {column} NOT IN ({placeholders})", tuple(excluded)


def _active_row(conn: sqlite3.Connection, employee_id: int):
    """Return the single active (effective_until IS NULL) row for an
    employee, or None. Invariant: at most one active row per employee.
    """
    return conn.execute(
        "SELECT id, effective_from FROM outlier_exclusions "
        "WHERE employee_id = ? AND effective_until IS NULL",
        (employee_id,),
    ).fetchone()


def exclude_employee(
    conn: sqlite3.Connection, employee_id: int, active_month: str
) -> None:
    """Exclude an employee starting from `active_month` ("YYYY-MM").

    No-op if the employee already has an active exclusion row.
    """
    if _active_row(conn, employee_id) is not None:
        return
    conn.execute(
        "INSERT INTO outlier_exclusions "
        "(employee_id, effective_from, effective_until, created_at) "
        "VALUES (?, ?, NULL, ?)",
        (employee_id, active_month,
         datetime.now(UTC).isoformat(timespec="seconds")),
    )


def revert_employee(
    conn: sqlite3.Connection, employee_id: int, active_month: str
) -> None:
    """Stop excluding an employee, effective from `active_month` onward.

    Soft revert (history-preserving):
      - if the active row started in `active_month` → DELETE it (empty range)
      - otherwise → set effective_until = active_month (past months stay excluded)
      - no active row → no-op
    """
    row = _active_row(conn, employee_id)
    if row is None:
        return
    if row["effective_from"] == active_month:
        conn.execute(
            "DELETE FROM outlier_exclusions WHERE id = ?", (row["id"],)
        )
    else:
        conn.execute(
            "UPDATE outlier_exclusions SET effective_until = ? WHERE id = ?",
            (active_month, row["id"]),
        )
