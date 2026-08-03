"""Pengecualian pegawai khusus layar Rekap Dinas Paparan.

Terpisah dari `outlier_exclusions`: yang itu berbasis periode dan dipakai
Dashboard/Heatmap/Coaching. Yang ini permanen, sederhana, dan hanya
mempengaruhi satu layar — mis. pegawai yang memang tak pernah bertugas
dinas sehingga hanya meramaikan daftar.
"""
import sqlite3
from datetime import datetime, UTC
from typing import Iterable, List


def list_excluded_ids(conn: sqlite3.Connection) -> set:
    """Set employee_id yang disembunyikan dari Rekap Dinas Paparan."""
    return {
        r["employee_id"]
        for r in conn.execute("SELECT employee_id FROM dinas_recap_exclusions")
    }


def set_excluded_ids(conn: sqlite3.Connection, employee_ids: Iterable[int]) -> None:
    """Ganti seluruh daftar pengecualian dengan `employee_ids` (idempoten)."""
    now = datetime.now(UTC).isoformat(timespec="seconds")
    wanted = {int(i) for i in employee_ids}
    conn.execute("DELETE FROM dinas_recap_exclusions")
    if wanted:
        conn.executemany(
            "INSERT INTO dinas_recap_exclusions (employee_id, created_at) "
            "VALUES (?, ?)",
            [(eid, now) for eid in sorted(wanted)],
        )


def list_employees_with_exclusion(conn: sqlite3.Connection) -> List[dict]:
    """Semua pegawai aktif + tanda apakah sedang dikecualikan.

    Feeds dialog 'Kelola Pengecualian'. Urut nama."""
    rows = conn.execute(
        """
        SELECT e.id AS employee_id, e.nama, e.dept,
               (x.employee_id IS NOT NULL) AS excluded
          FROM employees e
          LEFT JOIN dinas_recap_exclusions x ON x.employee_id = e.id
         WHERE e.active = 1
         ORDER BY e.nama ASC
        """
    ).fetchall()
    return [
        {"employee_id": r["employee_id"], "nama": r["nama"],
         "dept": r["dept"] or "", "excluded": bool(r["excluded"])}
        for r in rows
    ]
