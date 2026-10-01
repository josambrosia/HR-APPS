"""Verification decisions for overtime rows (v26).

Open = ketiadaan baris di tabel ini. Status selain open di-upsert; kembali
ke open menghapus baris. ``detected_minutes_at_decision`` menyimpan snapshot
angka yang terdeteksi saat aksi verifikasi terakhir, sehingga UI bisa
menandai "data berubah" bila absensi dikoreksi setelah keputusan.
"""
import sqlite3
from datetime import UTC, datetime

VALID_STATUSES = ("open", "diajukan", "diterima", "tidak_diterima")


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def get_decision(conn: sqlite3.Connection, employee_id: int,
                 tanggal: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM overtime_decisions WHERE employee_id = ? AND tanggal = ?",
        (employee_id, tanggal),
    ).fetchone()
    return dict(row) if row else None


def apply_status(conn: sqlite3.Connection, *, employee_id: int, tanggal: str,
                 status: str, detected_minutes: int | None,
                 approved_minutes: int | None = None,
                 note: str | None = None, now: str | None = None) -> None:
    if status not in VALID_STATUSES:
        raise ValueError(f"status tidak dikenal: {status!r}")
    if status == "open":
        conn.execute(
            "DELETE FROM overtime_decisions WHERE employee_id = ? AND tanggal = ?",
            (employee_id, tanggal),
        )
        return
    ts = now or _now()
    existing = get_decision(conn, employee_id, tanggal)
    submitted_at = (existing or {}).get("submitted_at") or ts
    decided_at = ts if status in ("diterima", "tidak_diterima") else None
    conn.execute(
        """
        INSERT INTO overtime_decisions
            (employee_id, tanggal, status, approved_minutes,
             detected_minutes_at_decision, note, submitted_at, decided_at,
             updated_at)
        VALUES (?,?,?,?,?,?,?,?,?)
        ON CONFLICT(employee_id, tanggal) DO UPDATE SET
            status = excluded.status,
            approved_minutes = excluded.approved_minutes,
            detected_minutes_at_decision = excluded.detected_minutes_at_decision,
            note = COALESCE(excluded.note, overtime_decisions.note),
            submitted_at = excluded.submitted_at,
            decided_at = excluded.decided_at,
            updated_at = excluded.updated_at
        """,
        (employee_id, tanggal, status, approved_minutes, detected_minutes,
         note, submitted_at, decided_at, ts),
    )


def set_note_approved(conn: sqlite3.Connection, *, employee_id: int,
                      tanggal: str, note: str | None,
                      approved_minutes: int | None,
                      now: str | None = None) -> None:
    """Simpan catatan/jam disetujui tanpa mengubah status (no-op bila Open)."""
    if get_decision(conn, employee_id, tanggal) is None:
        return
    ts = now or _now()
    conn.execute(
        "UPDATE overtime_decisions SET note = ?, approved_minutes = ?, "
        "updated_at = ? WHERE employee_id = ? AND tanggal = ?",
        (note, approved_minutes, ts, employee_id, tanggal),
    )
