import sqlite3
from datetime import datetime, UTC
from typing import Optional


def upsert_attendance(
    conn: sqlite3.Connection,
    *,
    employee_id: int,
    tanggal: str,
    hari: Optional[str],
    tipe: Optional[str],
    jadwal: Optional[str],
    masuk: Optional[str],
    keluar: Optional[str],
    kerja_jam: Optional[float],
    lembur_jam: Optional[float],
    terlambat_menit: Optional[int],
    has_issue: int,
    imported_from: str,
) -> None:
    """Insert or update an attendance row. PRESERVES reason_category, reason_detail,
    resolved_at on conflict — those fields are user-owned, not raw fingerprint data."""
    now = datetime.now(UTC).isoformat(timespec="seconds")
    conn.execute(
        """
        INSERT INTO attendance_records (
            employee_id, tanggal, hari, tipe, jadwal, masuk, keluar,
            kerja_jam, lembur_jam, terlambat_menit, has_issue,
            imported_from, imported_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(employee_id, tanggal) DO UPDATE SET
            hari = excluded.hari,
            tipe = excluded.tipe,
            jadwal = excluded.jadwal,
            masuk = excluded.masuk,
            keluar = excluded.keluar,
            kerja_jam = excluded.kerja_jam,
            lembur_jam = excluded.lembur_jam,
            terlambat_menit = excluded.terlambat_menit,
            has_issue = excluded.has_issue,
            imported_from = excluded.imported_from,
            imported_at = excluded.imported_at
            -- reason_category, reason_detail, resolved_at NOT updated (preserved)
        """,
        (employee_id, tanggal, hari, tipe, jadwal, masuk, keluar,
         kerja_jam, lembur_jam, terlambat_menit, has_issue,
         imported_from, now),
    )


def set_reason(
    conn: sqlite3.Connection,
    *,
    attendance_id: int,
    category: str,
    detail: Optional[str],
) -> None:
    now = datetime.now(UTC).isoformat(timespec="seconds")
    conn.execute(
        """
        UPDATE attendance_records
           SET reason_category = ?,
               reason_detail = ?,
               resolved_at = ?
         WHERE id = ?
        """,
        (category, detail, now, attendance_id),
    )


def list_open_issues(conn: sqlite3.Connection):
    return conn.execute(
        """
        SELECT ar.*, e.nama, e.dept, e.no_staff
          FROM attendance_records ar
          JOIN employees e ON ar.employee_id = e.id
         WHERE ar.has_issue = 1 AND ar.reason_category IS NULL
         ORDER BY ar.tanggal, e.nama
        """
    ).fetchall()


def list_all_for_period(
    conn: sqlite3.Connection, start: str, end: str
):
    return conn.execute(
        """
        SELECT ar.*, e.nama, e.dept, e.no_staff
          FROM attendance_records ar
          JOIN employees e ON ar.employee_id = e.id
         WHERE ar.tanggal BETWEEN ? AND ?
         ORDER BY ar.tanggal, e.nama
        """,
        (start, end),
    ).fetchall()


def list_issues_for_period(
    conn: sqlite3.Connection,
    start: str,
    end: str,
    resolved: Optional[bool] = None,
):
    """List has_issue=1 rows in [start,end], sorted by nama then tanggal.

    resolved=None  → both open and resolved
    resolved=False → only open (reason_category IS NULL)
    resolved=True  → only resolved (reason_category IS NOT NULL)
    """
    base_sql = """
        SELECT ar.*, e.nama, e.dept, e.no_staff
          FROM attendance_records ar
          JOIN employees e ON ar.employee_id = e.id
         WHERE ar.has_issue = 1
           AND ar.tanggal BETWEEN ? AND ?
    """
    params = [start, end]
    if resolved is True:
        base_sql += " AND ar.reason_category IS NOT NULL"
    elif resolved is False:
        base_sql += " AND ar.reason_category IS NULL"
    base_sql += " ORDER BY e.nama ASC, ar.tanggal ASC"
    return conn.execute(base_sql, params).fetchall()


def count_issues_for_period(conn: sqlite3.Connection, start: str, end: str):
    """Return {open, resolved, na, total} counts for has_issue=1 rows in range."""
    row = conn.execute(
        """
        SELECT
            SUM(CASE WHEN reason_category IS NULL THEN 1 ELSE 0 END) AS open_cnt,
            SUM(CASE WHEN reason_category IS NOT NULL AND reason_category != 'na' THEN 1 ELSE 0 END) AS resolved_cnt,
            SUM(CASE WHEN reason_category = 'na' THEN 1 ELSE 0 END) AS na_cnt,
            COUNT(*) AS total_cnt
          FROM attendance_records
         WHERE has_issue = 1
           AND tanggal BETWEEN ? AND ?
        """,
        (start, end),
    ).fetchone()
    return {
        "open": row["open_cnt"] or 0,
        "resolved": row["resolved_cnt"] or 0,
        "na": row["na_cnt"] or 0,
        "total": row["total_cnt"] or 0,
    }


def reset_month(conn: sqlite3.Connection) -> None:
    """Wipe all attendance data — for 'Mulai Bulan Baru' workflow."""
    conn.execute("DELETE FROM attendance_records")


def list_months_with_stats(conn: sqlite3.Connection):
    """List all months present in attendance_records with per-month stats,
    ordered newest-first.

    Returns rows (sqlite3.Row) with columns:
      - year_month: str ("YYYY-MM")
      - hari_count: int (distinct dates with records)
      - records_count: int (total rows)
      - open_issues_count: int (has_issue=1 AND reason_category IS NULL)
    """
    return conn.execute(
        """
        SELECT
            substr(tanggal, 1, 7) AS year_month,
            COUNT(DISTINCT tanggal) AS hari_count,
            COUNT(*) AS records_count,
            SUM(CASE
                WHEN has_issue = 1 AND reason_category IS NULL THEN 1
                ELSE 0
            END) AS open_issues_count
          FROM attendance_records
         GROUP BY year_month
         ORDER BY year_month DESC
        """
    ).fetchall()
