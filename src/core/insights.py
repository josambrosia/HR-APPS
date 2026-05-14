import sqlite3
from typing import List, Optional

from src.config import COACHING_EXCLUDED
from src.db.outlier import excluded_employee_ids, exclusion_sql


def terlambat_ranking(
    conn: sqlite3.Connection, start: str, end: str
) -> List[dict]:
    """Ranking lengkap karyawan untuk periode tertentu, urut by severity.

    A row contributes to terlambat aggregations only if the employee
    actually clocked in (`masuk IS NOT NULL`). Truly absent days
    (both masuk AND keluar NULL on Hari Kerja) are counted separately
    as `tidak_hadir` (alias: `absent_count`).

    Each returned dict has keys:
        id, nama, no_staff, dept,
        total_terlambat (sum of terlambat_menit > 0, excluding work-justified
                         reason_category in COACHING_EXCLUDED),
        hari_telat (count of late events, excluding work-justified),
        tidak_hadir (Hari Kerja days where masuk AND keluar both NULL),
        absent_count (alias of tidak_hadir — additive new field for
                      "Ranking Lengkap" print panel),
        issue_count (has_issue=1 row count).

    Sort: total_terlambat DESC, absent_count DESC, hari_telat DESC, nama ASC.
    Includes employees who only have absences (no late events) so the
    "Ranking Lengkap" print panel shows ALL active employees of the period.
    """
    placeholders = ",".join("?" for _ in COACHING_EXCLUDED)
    sql = f"""
        SELECT e.id, e.nama, e.no_staff, e.dept,
               SUM(CASE WHEN ar.reason_category IN ({placeholders}) THEN 0
                        WHEN ar.masuk IS NULL THEN 0
                        ELSE COALESCE(ar.terlambat_menit, 0) END) AS total_terlambat,
               COUNT(CASE WHEN ar.masuk IS NOT NULL
                          AND ar.terlambat_menit > 0
                          AND (ar.reason_category IS NULL
                               OR ar.reason_category NOT IN ({placeholders}))
                          THEN 1 END) AS hari_telat,
               SUM(CASE WHEN ar.tipe = 'Hari Kerja'
                          AND ar.masuk IS NULL AND ar.keluar IS NULL
                        THEN 1 ELSE 0 END) AS tidak_hadir,
               SUM(CASE WHEN ar.has_issue = 1 THEN 1 ELSE 0 END) AS issue_count
          FROM attendance_records ar
          JOIN employees e ON ar.employee_id = e.id
         WHERE ar.tanggal BETWEEN ? AND ?
         GROUP BY e.id
    """
    params = (*COACHING_EXCLUDED, *COACHING_EXCLUDED, start, end)
    rows = conn.execute(sql, params).fetchall()

    # Drop employees excluded via the Outlier menu for this period's month
    excluded = excluded_employee_ids(conn, start[:7])
    if excluded:
        rows = [r for r in rows if r["id"] not in excluded]

    result = [
        {
            "id": r["id"],
            "nama": r["nama"],
            "no_staff": r["no_staff"] or "",
            "dept": r["dept"] or "",
            "total_terlambat": r["total_terlambat"] or 0,
            "hari_telat": r["hari_telat"] or 0,
            "tidak_hadir": r["tidak_hadir"] or 0,
            "absent_count": r["tidak_hadir"] or 0,
            "issue_count": r["issue_count"] or 0,
        }
        for r in rows
    ]

    # Sort: total_terlambat DESC, absent_count DESC, hari_telat DESC, nama ASC
    result.sort(key=lambda r: (
        -r["total_terlambat"],
        -r["absent_count"],
        -r["hari_telat"],
        r["nama"],
    ))
    return result


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
    excluded = excluded_employee_ids(conn, start[:7])
    exc_frag, exc_params = exclusion_sql(excluded, column="e.id")
    sql = f"""
        SELECT e.id, e.nama, e.dept,
               SUM(CASE WHEN ar.reason_category IN ({placeholders}) THEN 0
                        WHEN ar.masuk IS NULL THEN 0
                        ELSE COALESCE(ar.terlambat_menit, 0) END)
                 + SUM(CASE WHEN ar.tipe='Hari Kerja' AND ar.masuk IS NULL AND ar.keluar IS NULL
                            THEN 60 ELSE 0 END)
                 + SUM(CASE WHEN ar.has_issue = 1 THEN 30 ELSE 0 END) AS score,
               COUNT(*) AS hari_kerja
          FROM attendance_records ar
          JOIN employees e ON ar.employee_id = e.id
         WHERE ar.tanggal BETWEEN ? AND ?
               AND ar.tipe = 'Hari Kerja'{exc_frag}
         GROUP BY e.id
         HAVING hari_kerja >= 3
         ORDER BY score ASC, e.nama ASC
         LIMIT 1
    """
    params = (*COACHING_EXCLUDED, start, end, *exc_params)
    return conn.execute(sql, params).fetchone()


def karyawan_teladan_top_n(
    conn: sqlite3.Connection, start: str, end: str, n: Optional[int] = 5
) -> List[sqlite3.Row]:
    """Top N best performers (lowest composite score).

    If `n` is None, returns ALL teladan (no limit). Default n=5 preserves
    backward compat with existing callers (UI dashboard, etc.).
    """
    placeholders = ",".join("?" for _ in COACHING_EXCLUDED)
    excluded = excluded_employee_ids(conn, start[:7])
    exc_frag, exc_params = exclusion_sql(excluded, column="e.id")
    limit_clause = "" if n is None else "LIMIT ?"
    sql = f"""
        SELECT e.id, e.nama, e.dept,
               SUM(CASE WHEN ar.reason_category IN ({placeholders}) THEN 0
                        WHEN ar.masuk IS NULL THEN 0
                        ELSE COALESCE(ar.terlambat_menit, 0) END)
                 + SUM(CASE WHEN ar.tipe='Hari Kerja' AND ar.masuk IS NULL AND ar.keluar IS NULL
                            THEN 60 ELSE 0 END)
                 + SUM(CASE WHEN ar.has_issue = 1 THEN 30 ELSE 0 END) AS score,
               COUNT(*) AS hari_kerja
          FROM attendance_records ar
          JOIN employees e ON ar.employee_id = e.id
         WHERE ar.tanggal BETWEEN ? AND ?
               AND ar.tipe = 'Hari Kerja'{exc_frag}
         GROUP BY e.id
         HAVING hari_kerja >= 3
         ORDER BY score ASC, e.nama ASC
         {limit_clause}
    """
    if n is None:
        params = (*COACHING_EXCLUDED, start, end, *exc_params)
    else:
        params = (*COACHING_EXCLUDED, start, end, *exc_params, n)
    return conn.execute(sql, params).fetchall()


def ranking_departemen(
    conn: sqlite3.Connection, start: str, end: str
) -> List[sqlite3.Row]:
    placeholders = ",".join("?" for _ in COACHING_EXCLUDED)
    sql = f"""
        SELECT e.dept,
               SUM(CASE WHEN ar.reason_category IN ({placeholders}) THEN 0
                        WHEN ar.masuk IS NULL THEN 0
                        ELSE COALESCE(ar.terlambat_menit, 0) END) AS total_terlambat,
               SUM(CASE WHEN ar.has_issue = 1 THEN 1 ELSE 0 END) AS issue_count,
               COUNT(CASE WHEN ar.masuk IS NOT NULL
                          AND ar.terlambat_menit > 0
                          AND (ar.reason_category IS NULL
                               OR ar.reason_category NOT IN ({placeholders}))
                          THEN 1 END) AS hari_telat,
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
    """Weekday breakdown sorted by terlambat_count DESC.

    Terlambat counts only rows where the employee actually clocked in.
    """
    sql = """
        SELECT hari,
               SUM(CASE WHEN masuk IS NOT NULL AND terlambat_menit > 0 THEN 1 ELSE 0 END) AS terlambat_count,
               SUM(CASE WHEN has_issue = 1 THEN 1 ELSE 0 END) AS issue_count,
               COUNT(*) AS total_rows
          FROM attendance_records
         WHERE tipe = 'Hari Kerja'
           AND tanggal BETWEEN ? AND ?
           AND hari IS NOT NULL
         GROUP BY hari
         ORDER BY terlambat_count DESC, hari ASC
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


def avg_minutes_per_late_event(
    conn: sqlite3.Connection, period_start: str, period_end: str
) -> float:
    """Rata-rata menit terlambat per kejadian (total_min / count of late events).

    Returns 0.0 jika tidak ada late events di periode tersebut.
    Rows dengan terlambat_menit=0 atau NULL (= on time / absent) tidak
    dihitung sebagai event.
    """
    row = conn.execute(
        """
        SELECT COALESCE(SUM(terlambat_menit), 0) AS total,
               COUNT(*) AS cnt
          FROM attendance_records
         WHERE tanggal BETWEEN ? AND ?
           AND tipe = 'Hari Kerja'
           AND terlambat_menit IS NOT NULL
           AND terlambat_menit > 0
        """,
        (period_start, period_end),
    ).fetchone()
    total, cnt = row[0], row[1]
    return float(total) / cnt if cnt else 0.0


_POLA_JAM_BANDS = [
    ('<07:45',      'early'),
    ('07:45-07:59', 'early'),
    ('08:00',       'ontime'),
    ('08:01-08:05', 'mild'),
    ('08:06-08:15', 'mild'),
    ('08:16-08:30', 'mod'),
    ('08:31-09:00', 'severe'),
    ('>09:00',      'chronic'),
]


def _classify_jam_masuk(masuk: str) -> str:
    """Map HH:MM string to band label. Caller already filters masuk IS NOT NULL."""
    if masuk < '07:45':    return '<07:45'
    if masuk < '08:00':    return '07:45-07:59'
    if masuk == '08:00':   return '08:00'
    if masuk <= '08:05':   return '08:01-08:05'
    if masuk <= '08:15':   return '08:06-08:15'
    if masuk <= '08:30':   return '08:16-08:30'
    if masuk <= '09:00':   return '08:31-09:00'
    return '>09:00'


def pola_jam_masuk(
    conn: sqlite3.Connection, period_start: str, period_end: str
) -> list[dict]:
    """Distribusi 8-band waktu kedatangan untuk sesi present (masuk IS NOT NULL).

    Returns: list of 8 dicts (chronological), even bands dengan count=0.
        [{'band': '<07:45', 'count': int, 'severity': 'early'}, ...]

    Severity mapping:
        early   — datang sebelum 08:00
        ontime  — 08:00 pas
        mild    — 1-15 min terlambat (08:01-08:15)
        mod     — 16-30 min terlambat (08:16-08:30)
        severe  — 31-60 min terlambat (08:31-09:00)
        chronic — > 60 min terlambat (>09:00)
    """
    rows = conn.execute(
        """
        SELECT masuk
          FROM attendance_records
         WHERE tanggal BETWEEN ? AND ?
           AND tipe = 'Hari Kerja'
           AND masuk IS NOT NULL
        """,
        (period_start, period_end),
    ).fetchall()

    counts = {band: 0 for band, _ in _POLA_JAM_BANDS}
    for (masuk,) in rows:
        counts[_classify_jam_masuk(masuk)] += 1

    return [
        {'band': band, 'count': counts[band], 'severity': severity}
        for band, severity in _POLA_JAM_BANDS
    ]
