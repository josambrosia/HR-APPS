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
