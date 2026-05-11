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
