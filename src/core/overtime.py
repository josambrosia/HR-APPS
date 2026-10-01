"""Overtime detection + monthly aggregation (v26). Pure, no Tk.

Aturan (spec §3):
- Hari kerja: keluar > max(ambang, jam pulang); durasi = keluar − jam pulang.
- Hari libur/akhir pekan: masuk & keluar terisi; durasi = keluar − masuk.
- Baris Open tidak disimpan; keputusan menempel di ``overtime_decisions``.
- Baris yang pernah diputus tetap ditampilkan walau kini tidak lagi memenuhi
  syarat (``qualifies=False``), supaya keputusan tidak hilang.
"""
import calendar
import sqlite3
from dataclasses import dataclass
from datetime import date

from src.core.attendance_calc import to_minutes
from src.db.holidays import holiday_dates_in_month
from src.db.schedule import schedule_for
from src.db.settings import read_overtime_threshold


@dataclass(frozen=True)
class OvertimeRow:
    employee_id: int
    nama: str
    dept: str | None
    tanggal: str
    hari: str | None
    tipe: str | None
    masuk: str | None
    keluar: str | None
    minutes: int
    is_holiday: bool
    qualifies: bool
    status: str
    approved_minutes: int | None
    note: str | None
    submitted_at: str | None
    decided_at: str | None
    detected_at_decision: int | None

    @property
    def changed(self) -> bool:
        """True bila absensi berubah setelah keputusan terakhir."""
        return (self.status != "open"
                and self.detected_at_decision is not None
                and self.detected_at_decision != self.minutes)


def threshold_minutes(conn: sqlite3.Connection) -> int:
    raw = read_overtime_threshold(conn)
    return to_minutes(raw) or 18 * 60


def detect_minutes(*, tipe, masuk, keluar, schedule, threshold_min,
                   is_holiday) -> int | None:
    """Menit lembur untuk satu baris, atau None bila bukan kandidat."""
    ms, ks = to_minutes(masuk), to_minutes(keluar)
    if ms is None or ks is None:
        return None
    if is_holiday:
        minutes = ks - ms
        return minutes if minutes > 0 else None
    if tipe != "Hari Kerja":
        return None
    end_m = to_minutes(schedule[1])
    if end_m is None:
        return None
    if ks <= threshold_min or ks <= end_m:
        return None
    return ks - end_m


def _month_bounds(year_month: str) -> tuple[str, str]:
    y, m = int(year_month[:4]), int(year_month[5:7])
    last = calendar.monthrange(y, m)[1]
    return f"{year_month}-01", f"{year_month}-{last:02d}"


def month_rows(conn: sqlite3.Connection, year_month: str) -> list[OvertimeRow]:
    start, end = _month_bounds(year_month)
    threshold = threshold_minutes(conn)
    holidays = holiday_dates_in_month(conn, year_month)
    raw = conn.execute(
        """
        SELECT ar.employee_id, e.nama, e.dept, ar.tanggal, ar.hari, ar.tipe,
               ar.masuk, ar.keluar,
               od.status, od.approved_minutes, od.note,
               od.submitted_at, od.decided_at, od.detected_minutes_at_decision
          FROM attendance_records ar
          JOIN employees e ON e.id = ar.employee_id
          LEFT JOIN overtime_decisions od
                 ON od.employee_id = ar.employee_id AND od.tanggal = ar.tanggal
         WHERE ar.tanggal BETWEEN ? AND ?
         ORDER BY ar.tanggal ASC, e.nama ASC
        """,
        (start, end),
    ).fetchall()
    sched_cache: dict[str, tuple[str, str]] = {}
    out: list[OvertimeRow] = []
    for r in raw:
        tgl = r["tanggal"]
        if tgl not in sched_cache:
            sched_cache[tgl] = schedule_for(conn, tgl)
        d = date.fromisoformat(tgl)
        is_holiday = (d.weekday() >= 5 or tgl in holidays
                      or r["tipe"] == "Hari Libur")
        minutes = detect_minutes(
            tipe=r["tipe"], masuk=r["masuk"], keluar=r["keluar"],
            schedule=sched_cache[tgl], threshold_min=threshold,
            is_holiday=is_holiday)
        has_decision = r["status"] is not None
        if minutes is None and not has_decision:
            continue
        out.append(OvertimeRow(
            employee_id=r["employee_id"], nama=r["nama"], dept=r["dept"],
            tanggal=tgl, hari=r["hari"], tipe=r["tipe"],
            masuk=r["masuk"], keluar=r["keluar"],
            minutes=minutes or 0, is_holiday=is_holiday,
            qualifies=minutes is not None,
            status=r["status"] or "open",
            approved_minutes=r["approved_minutes"], note=r["note"],
            submitted_at=r["submitted_at"], decided_at=r["decided_at"],
            detected_at_decision=r["detected_minutes_at_decision"]))
    return out


def count_pending(conn: sqlite3.Connection, year_month: str) -> int:
    """Open + Diajukan (belum final) — untuk badge Dashboard/sidebar."""
    return sum(1 for r in month_rows(conn, year_month)
               if r.status in ("open", "diajukan"))


def summarize(rows: list[OvertimeRow]) -> list[dict]:
    """Total per karyawan: hari, jam terdeteksi, jam disetujui."""
    agg: dict[int, dict] = {}
    for r in rows:
        a = agg.setdefault(r.employee_id, {
            "employee_id": r.employee_id, "nama": r.nama, "dept": r.dept,
            "days": 0, "detected": 0, "approved": 0})
        a["days"] += 1
        a["detected"] += r.minutes
        if r.status == "diterima":
            a["approved"] += r.approved_minutes or 0
    return sorted(agg.values(), key=lambda a: a["detected"], reverse=True)


def format_duration(minutes: int) -> str:
    h, m = divmod(max(0, int(minutes)), 60)
    if h and m:
        return f"{h}j {m}m"
    if h:
        return f"{h}j"
    return f"{m}m"
