"""Data access for the Hari Libur feature.

Holidays are date-keyed (company-wide). The `holidays` table is the durable
source of truth; attendance_records.tipe is stamped 'Hari Libur' as a
denormalisation so weekly export & other queries see it directly. The stamp
is re-applied after every import via restamp_holidays().
"""
import sqlite3
from typing import List


def list_holidays(conn: sqlite3.Connection) -> List[str]:
    """All holiday dates ('YYYY-MM-DD'), ascending."""
    rows = conn.execute(
        "SELECT tanggal FROM holidays ORDER BY tanggal ASC"
    ).fetchall()
    return [r[0] for r in rows]


def holiday_dates_in_month(conn: sqlite3.Connection, year_month: str) -> set:
    """Set of holiday dates within the given 'YYYY-MM' month."""
    rows = conn.execute(
        "SELECT tanggal FROM holidays WHERE substr(tanggal, 1, 7) = ?",
        (year_month,),
    ).fetchall()
    return {r[0] for r in rows}


def workday_roster(conn: sqlite3.Connection, year_month: str) -> List[dict]:
    """Dates in the month with attendance records of tipe Hari Kerja/Hari Libur.

    Each dict: {tanggal, hari, is_holiday, issue_count}.
      - is_holiday: date is present in the holidays table
      - issue_count: if NOT holiday -> count of OPEN issues (has_issue=1 AND
        reason_category IS NULL) -> preview "will be auto-resolved".
        If holiday -> count of reason_category='libur' rows -> preview
        "will be re-opened" on revert.
    Sorted ascending by date. Istirahat (weekend) rows are excluded —
    marking those as holiday is meaningless.
    """
    rows = conn.execute(
        """
        SELECT
            ar.tanggal,
            MIN(ar.hari) AS hari,
            MAX(CASE WHEN h.tanggal IS NOT NULL THEN 1 ELSE 0 END) AS is_holiday,
            SUM(CASE
                WHEN h.tanggal IS NULL
                     AND ar.has_issue = 1 AND ar.reason_category IS NULL
                THEN 1
                WHEN h.tanggal IS NOT NULL
                     AND ar.reason_category = 'libur'
                THEN 1
                ELSE 0
            END) AS issue_count
          FROM attendance_records ar
          LEFT JOIN holidays h ON h.tanggal = ar.tanggal
         WHERE substr(ar.tanggal, 1, 7) = ?
           AND ar.tipe IN ('Hari Kerja', 'Hari Libur')
         GROUP BY ar.tanggal
         ORDER BY ar.tanggal ASC
        """,
        (year_month,),
    ).fetchall()
    return [
        {
            "tanggal": r["tanggal"],
            "hari": r["hari"] or "",
            "is_holiday": bool(r["is_holiday"]),
            "issue_count": r["issue_count"] or 0,
        }
        for r in rows
    ]
