import sqlite3
from datetime import datetime
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
    now = datetime.utcnow().isoformat(timespec="seconds")
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
    now = datetime.utcnow().isoformat(timespec="seconds")
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


def reset_month(conn: sqlite3.Connection) -> None:
    """Wipe all attendance data — for 'Mulai Bulan Baru' workflow."""
    conn.execute("DELETE FROM attendance_records")
