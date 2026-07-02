import sqlite3
from datetime import datetime, UTC
from typing import Optional

from src.db.employees import get_employee_by_no_staff


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


def count_summary_for_period(conn: sqlite3.Connection, start: str, end: str) -> dict:
    """Return {employees, issues, unresolved} counts for rows in [start, end].

    employees  — distinct employee_id with any record in range
    issues     — has_issue=1 rows
    unresolved — has_issue=1 AND reason_category IS NULL (still open)

    Used by the Export screen's active-month banner summary line.
    """
    row = conn.execute(
        """
        SELECT
            COUNT(DISTINCT employee_id) AS emp_count,
            SUM(CASE WHEN has_issue = 1 THEN 1 ELSE 0 END) AS issue_count,
            SUM(CASE WHEN has_issue = 1 AND reason_category IS NULL THEN 1 ELSE 0 END) AS unresolved_count
          FROM attendance_records
         WHERE tanggal BETWEEN ? AND ?
        """,
        (start, end),
    ).fetchone()
    return {
        "employees": row["emp_count"] or 0,
        "issues": row["issue_count"] or 0,
        "unresolved": row["unresolved_count"] or 0,
    }


def list_severe_lateness_for_period(conn, start, end, threshold_min, resolved=None):
    """Hari Kerja rows with both punches present and terlambat_menit >=
    threshold_min, in [start, end]. resolved=False -> reason_category IS NULL;
    True -> IS NOT NULL; None -> both. Joined with employees, sorted by name/date."""
    sql = """
        SELECT ar.*, e.nama, e.dept, e.no_staff
          FROM attendance_records ar
          JOIN employees e ON ar.employee_id = e.id
         WHERE ar.tipe = 'Hari Kerja'
           AND ar.masuk IS NOT NULL
           AND ar.keluar IS NOT NULL
           AND ar.terlambat_menit >= ?
           AND ar.tanggal BETWEEN ? AND ?
    """
    params = [threshold_min, start, end]
    if resolved is True:
        sql += " AND ar.reason_category IS NOT NULL"
    elif resolved is False:
        sql += " AND ar.reason_category IS NULL"
    sql += " ORDER BY e.nama ASC, ar.tanggal ASC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def count_severe_lateness_for_period(conn, start, end, threshold_min):
    """Returns {open, resolved, na, total} over the threshold-filtered set.
    resolved = reason set AND != 'na'; na = reason == 'na'; open = reason NULL."""
    row = conn.execute(
        """
        SELECT
          SUM(CASE WHEN reason_category IS NULL THEN 1 ELSE 0 END) AS open,
          SUM(CASE WHEN reason_category IS NOT NULL AND reason_category != 'na'
                   THEN 1 ELSE 0 END) AS resolved,
          SUM(CASE WHEN reason_category = 'na' THEN 1 ELSE 0 END) AS na,
          COUNT(*) AS total
          FROM attendance_records
         WHERE tipe = 'Hari Kerja'
           AND masuk IS NOT NULL AND keluar IS NOT NULL
           AND terlambat_menit >= ?
           AND tanggal BETWEEN ? AND ?
        """,
        (threshold_min, start, end),
    ).fetchone()
    return {
        "open": row["open"] or 0,
        "resolved": row["resolved"] or 0,
        "na": row["na"] or 0,
        "total": row["total"] or 0,
    }


def reset_month(conn: sqlite3.Connection) -> None:
    """Wipe all attendance data — legacy 'Mulai Bulan Baru' workflow.

    NOTE: No longer called from the UI (button removed when multi-month
    support landed). Kept intentionally for future scripted/admin use
    (e.g., per-month delete from Riwayat Bulan context menu).
    """
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


def unresolve_issue(conn: sqlite3.Connection, *, attendance_id: int) -> None:
    """Clear resolve state on an attendance row.

    Sets reason_category, reason_detail, resolved_at all to NULL. The row
    becomes "Open" again. Used by the Issues 'Batalkan Resolve' button.
    """
    conn.execute(
        """
        UPDATE attendance_records
           SET reason_category = NULL,
               reason_detail = NULL,
               resolved_at = NULL
         WHERE id = ?
        """,
        (attendance_id,),
    )


def list_recent_imports(
    conn: sqlite3.Connection, limit: int = 5,
) -> list[dict]:
    """Return recent fingerprint imports — distinct imported_from with metadata.

    Each dict has keys: imported_from, imported_at, emp_count.
    Sorted by imported_at DESC (latest first). Limit caller-provided.

    Used by Import screen's 'Riwayat Import Terakhir' history list.
    """
    rows = conn.execute(
        """
        SELECT
            imported_from,
            MAX(imported_at) AS imported_at,
            COUNT(DISTINCT employee_id) AS emp_count
        FROM attendance_records
        WHERE imported_from IS NOT NULL
        GROUP BY imported_from
        ORDER BY MAX(imported_at) DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def count_overlap(conn: sqlite3.Connection, pending_rows: list) -> dict:
    """Count how many pending rows would overwrite existing DB rows.

    Returns dict with keys 'new' (would insert) and 'overwrite' (would
    replace existing row at (employee_id, tanggal) via upsert).

    The existing upsert preserves reason_category/reason_detail/resolved_at,
    so 'overwrite' is data-only — user input is not destroyed. UI should
    surface this count so the user knows scope but not raise alarm.

    Uses N+1 lookup pattern (employees + per-row attendance check).
    Typical input < 200 rows, acceptable at SQLite speeds.
    """
    new_count = 0
    overwrite_count = 0
    for r in pending_rows:
        emp = get_employee_by_no_staff(conn, r.no_staff)
        if emp is None:
            new_count += 1
            continue
        existing = conn.execute(
            "SELECT 1 FROM attendance_records WHERE employee_id = ? AND tanggal = ?",
            (emp["id"], r.tanggal),
        ).fetchone()
        if existing:
            overwrite_count += 1
        else:
            new_count += 1
    return {"new": new_count, "overwrite": overwrite_count}


def list_attendance_matrix(conn, start, end):
    """All attendance rows in [start,end] joined with employee, for the heatmap.
    Returns only rows that exist; the renderer fills missing (employee,date)
    cells. Sorted by nama, tanggal."""
    sql = """
        SELECT ar.employee_id, e.nama, e.dept, ar.tanggal, ar.hari, ar.tipe,
               ar.masuk, ar.keluar, ar.terlambat_menit,
               ar.reason_category, ar.reason_detail, ar.has_issue
          FROM attendance_records ar
          JOIN employees e ON ar.employee_id = e.id
         WHERE ar.tanggal BETWEEN ? AND ?
         ORDER BY e.nama ASC, ar.tanggal ASC
    """
    return [dict(r) for r in conn.execute(sql, (start, end)).fetchall()]
