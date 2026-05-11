import sqlite3
from typing import List, Optional

from src.config import COACHING_EXCLUDED


def terlambat_ranking(
    conn: sqlite3.Connection, start: str, end: str
) -> List[sqlite3.Row]:
    """All employees ranked by total_terlambat DESC, excluding work-justified rows."""
    placeholders = ",".join("?" for _ in COACHING_EXCLUDED)
    sql = f"""
        SELECT e.id, e.nama, e.dept,
               SUM(CASE WHEN ar.reason_category IN ({placeholders}) THEN 0
                        ELSE COALESCE(ar.terlambat_menit, 0) END) AS total_terlambat,
               COUNT(CASE WHEN ar.terlambat_menit > 0
                          AND (ar.reason_category IS NULL
                               OR ar.reason_category NOT IN ({placeholders}))
                          THEN 1 END) AS hari_telat,
               SUM(CASE WHEN ar.has_issue = 1 THEN 1 ELSE 0 END) AS issue_count
          FROM attendance_records ar
          JOIN employees e ON ar.employee_id = e.id
         WHERE ar.tanggal BETWEEN ? AND ?
         GROUP BY e.id
         ORDER BY total_terlambat DESC
    """
    params = (*COACHING_EXCLUDED, *COACHING_EXCLUDED, start, end)
    return conn.execute(sql, params).fetchall()


def top_n_terlambat(
    conn: sqlite3.Connection, start: str, end: str, n: int = 5
) -> List[sqlite3.Row]:
    rows = terlambat_ranking(conn, start, end)
    # Drop zero-terlambat rows to avoid showing 28 names with all zeros
    return [r for r in rows if r["total_terlambat"] > 0][:n]


def coaching_flag(
    conn: sqlite3.Connection, start: str, end: str, threshold: int = 75
) -> List[sqlite3.Row]:
    return [r for r in terlambat_ranking(conn, start, end)
            if r["total_terlambat"] > threshold]


def karyawan_teladan(
    conn: sqlite3.Connection, start: str, end: str
) -> Optional[sqlite3.Row]:
    """Lowest composite score = best. Filter min 3 hari kerja (excludes long leave)."""
    placeholders = ",".join("?" for _ in COACHING_EXCLUDED)
    sql = f"""
        SELECT e.id, e.nama, e.dept,
               SUM(CASE WHEN ar.reason_category IN ({placeholders}) THEN 0
                        ELSE COALESCE(ar.terlambat_menit, 0) END)
                 + SUM(CASE WHEN ar.tipe='Hari Kerja' AND ar.masuk IS NULL AND ar.keluar IS NULL
                            THEN 60 ELSE 0 END)
                 + SUM(CASE WHEN ar.has_issue = 1 THEN 30 ELSE 0 END) AS score,
               COUNT(*) AS hari_kerja
          FROM attendance_records ar
          JOIN employees e ON ar.employee_id = e.id
         WHERE ar.tanggal BETWEEN ? AND ?
               AND ar.tipe = 'Hari Kerja'
         GROUP BY e.id
         HAVING hari_kerja >= 3
         ORDER BY score ASC, e.nama ASC
         LIMIT 1
    """
    params = (*COACHING_EXCLUDED, start, end)
    return conn.execute(sql, params).fetchone()


def karyawan_teladan_top_n(
    conn: sqlite3.Connection, start: str, end: str, n: int = 5
) -> List[sqlite3.Row]:
    """Top N pegawai with the LOWEST composite score (best performers).

    Composite formula:
        score = SUM(terlambat_menit excluding work-justified)
              + 60 * SUM(absen days)
              + 30 * SUM(issue_count)

    Filter: min 3 hari kerja in the period (excludes long-leave employees).
    Tie-break: alphabetical by nama.
    """
    placeholders = ",".join("?" for _ in COACHING_EXCLUDED)
    sql = f"""
        SELECT e.id, e.nama, e.dept,
               SUM(CASE WHEN ar.reason_category IN ({placeholders}) THEN 0
                        ELSE COALESCE(ar.terlambat_menit, 0) END)
                 + SUM(CASE WHEN ar.tipe='Hari Kerja' AND ar.masuk IS NULL AND ar.keluar IS NULL
                            THEN 60 ELSE 0 END)
                 + SUM(CASE WHEN ar.has_issue = 1 THEN 30 ELSE 0 END) AS score,
               COUNT(*) AS hari_kerja
          FROM attendance_records ar
          JOIN employees e ON ar.employee_id = e.id
         WHERE ar.tanggal BETWEEN ? AND ?
               AND ar.tipe = 'Hari Kerja'
         GROUP BY e.id
         HAVING hari_kerja >= 3
         ORDER BY score ASC, e.nama ASC
         LIMIT ?
    """
    params = (*COACHING_EXCLUDED, start, end, n)
    return conn.execute(sql, params).fetchall()


def ranking_departemen(
    conn: sqlite3.Connection, start: str, end: str
) -> List[sqlite3.Row]:
    """Departments ranked by total_terlambat DESC (excluding work-justified rows).

    Returns rows with: dept, total_terlambat, issue_count, hari_telat,
    pegawai_count (distinct employees with activity in period).
    """
    placeholders = ",".join("?" for _ in COACHING_EXCLUDED)
    sql = f"""
        SELECT e.dept,
               SUM(CASE WHEN ar.reason_category IN ({placeholders}) THEN 0
                        ELSE COALESCE(ar.terlambat_menit, 0) END) AS total_terlambat,
               SUM(CASE WHEN ar.has_issue = 1 THEN 1 ELSE 0 END) AS issue_count,
               SUM(CASE WHEN ar.terlambat_menit > 0
                          AND (ar.reason_category IS NULL
                               OR ar.reason_category NOT IN ({placeholders}))
                          THEN 1 ELSE 0 END) AS hari_telat,
               COUNT(DISTINCT e.id) AS pegawai_count
          FROM attendance_records ar
          JOIN employees e ON ar.employee_id = e.id
         WHERE ar.tanggal BETWEEN ? AND ?
               AND e.dept IS NOT NULL
         GROUP BY e.dept
         ORDER BY total_terlambat DESC, e.dept ASC
    """
    params = (*COACHING_EXCLUDED, *COACHING_EXCLUDED, start, end)
    return conn.execute(sql, params).fetchall()


def hari_paling_rawan(
    conn: sqlite3.Connection, start: str, end: str
) -> List[sqlite3.Row]:
    """Issue count per weekday (Hari Kerja only), sorted DESC.

    Returns rows: hari, issue_count, terlambat_count (rows where terlambat_menit > 0).
    Weekdays come from the `hari` column in attendance_records.
    """
    sql = """
        SELECT hari,
               SUM(CASE WHEN has_issue = 1 THEN 1 ELSE 0 END) AS issue_count,
               SUM(CASE WHEN terlambat_menit > 0 THEN 1 ELSE 0 END) AS terlambat_count,
               COUNT(*) AS total_rows
          FROM attendance_records
         WHERE tipe = 'Hari Kerja'
           AND tanggal BETWEEN ? AND ?
           AND hari IS NOT NULL
         GROUP BY hari
         ORDER BY issue_count DESC, terlambat_count DESC, hari ASC
    """
    return conn.execute(sql, (start, end)).fetchall()


def resolution_rate(
    conn: sqlite3.Connection, start: str, end: str
) -> dict:
    """Return {resolved, total, rate_pct} — what % of issues in range have a reason set."""
    row = conn.execute(
        """
        SELECT
            SUM(CASE WHEN reason_category IS NOT NULL THEN 1 ELSE 0 END) AS resolved,
            COUNT(*) AS total
          FROM attendance_records
         WHERE has_issue = 1 AND tanggal BETWEEN ? AND ?
        """,
        (start, end),
    ).fetchone()
    resolved = row["resolved"] or 0
    total = row["total"] or 0
    rate = (resolved / total * 100) if total > 0 else 0.0
    return {"resolved": resolved, "total": total, "rate_pct": round(rate, 1)}
