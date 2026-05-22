"""Data access for the Hari Libur feature.

Holidays are date-keyed (company-wide). The `holidays` table is the durable
source of truth; attendance_records.tipe is stamped 'Hari Libur' as a
denormalisation so weekly export & other queries see it directly. The stamp
is re-applied after every import via restamp_holidays().
"""
import sqlite3
from datetime import datetime, UTC
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


def mark_holidays(conn: sqlite3.Connection, dates: list) -> dict:
    """Mark the given dates ('YYYY-MM-DD') as holidays.

    For each date: insert into holidays, stamp attendance_records.tipe to
    'Hari Libur', auto-resolve OPEN issues (reason_category IS NULL) with
    reason_category='libur'. Idempotent — already-holiday dates re-stamp
    harmlessly. Returns {'dates_marked', 'issues_resolved'}.
    """
    now = datetime.now(UTC).isoformat(timespec="seconds")
    issues_resolved = 0
    for d in dates:
        conn.execute(
            "INSERT OR IGNORE INTO holidays (tanggal, created_at) VALUES (?, ?)",
            (d, now),
        )
        conn.execute(
            "UPDATE attendance_records SET tipe='Hari Libur' "
            "WHERE tanggal=? AND tipe='Hari Kerja'",
            (d,),
        )
        cur = conn.execute(
            "UPDATE attendance_records "
            "SET reason_category='libur', reason_detail=NULL, resolved_at=? "
            "WHERE tanggal=? AND has_issue=1 AND reason_category IS NULL",
            (now, d),
        )
        issues_resolved += cur.rowcount
    return {"dates_marked": len(dates), "issues_resolved": issues_resolved}


def unmark_holidays(conn: sqlite3.Connection, dates: list) -> dict:
    """Remove holiday status from the given dates.

    For each date: delete from holidays, restore attendance_records.tipe to
    'Hari Kerja', re-open ONLY issues this feature resolved
    (reason_category='libur'). Manual resolutions are left untouched.
    Returns {'dates_unmarked', 'issues_reopened'}.
    """
    issues_reopened = 0
    for d in dates:
        conn.execute("DELETE FROM holidays WHERE tanggal=?", (d,))
        conn.execute(
            "UPDATE attendance_records SET tipe='Hari Kerja' "
            "WHERE tanggal=? AND tipe='Hari Libur'",
            (d,),
        )
        cur = conn.execute(
            "UPDATE attendance_records "
            "SET reason_category=NULL, reason_detail=NULL, resolved_at=NULL "
            "WHERE tanggal=? AND reason_category='libur'",
            (d,),
        )
        issues_reopened += cur.rowcount
    return {"dates_unmarked": len(dates), "issues_reopened": issues_reopened}


def restamp_holidays(conn: sqlite3.Connection) -> None:
    """Re-apply holiday stamping for every date in the holidays table.

    Called after a fingerprint import: upsert_attendance overwrites
    attendance_records.tipe back to 'Hari Kerja', so this re-stamps
    'Hari Libur' and re-resolves any newly-imported OPEN issues on
    holiday dates. Makes import idempotent w.r.t. holiday status.
    """
    dates = [r[0] for r in conn.execute("SELECT tanggal FROM holidays")]
    if dates:
        mark_holidays(conn, dates)


def working_days_count(conn: sqlite3.Connection, start_iso: str, end_iso: str) -> int:
    """Count distinct dates with tipe='Hari Kerja' in [start_iso, end_iso] inclusive.

    Used by the Dashboard coaching panel and the standalone Coaching menu to
    scale the per-day threshold to the actual working days in the period.
    Hari Libur and Istirahat rows are automatically excluded by the tipe filter.
    Returns 0 if no fingerprint data has been imported for the period.
    """
    row = conn.execute(
        "SELECT COUNT(DISTINCT tanggal) FROM attendance_records "
        "WHERE tipe = 'Hari Kerja' AND tanggal BETWEEN ? AND ?",
        (start_iso, end_iso),
    ).fetchone()
    return int(row[0]) if row else 0
