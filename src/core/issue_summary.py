import sqlite3
from datetime import datetime

# Indonesian month names
_MONTH_ID = {
    1: "Januari", 2: "Februari", 3: "Maret", 4: "April",
    5: "Mei", 6: "Juni", 7: "Juli", 8: "Agustus",
    9: "September", 10: "Oktober", 11: "November", 12: "Desember",
}


def _format_date_id(iso_date: str) -> str:
    dt = datetime.strptime(iso_date, "%Y-%m-%d")
    return f"{dt.day} {_MONTH_ID[dt.month]} {dt.year}"


def _describe_kind(masuk, keluar) -> str:
    if masuk is None and keluar is None:
        return "tidak masuk"
    if masuk is None:
        return "lupa absen masuk"
    if keluar is None:
        return "lupa absen pulang"
    return "anomali"


def render_summary_for_employee(
    conn: sqlite3.Connection,
    employee_id: int,
    year_month: str | None = None,
) -> str:
    """Build a list-style WA-ready summary for an employee's open issues.

    Args:
        conn: SQLite connection.
        employee_id: Target employee ID.
        year_month: Optional 'YYYY-MM' filter. When provided, restricts issues
            to that month only (typically the active month from settings).
            When None, returns all open issues (legacy behavior, used by tests).

    Returns empty string if no open issues — caller decides what to do.
    Format:
        NAMA (N issue)
        - Hari, DD Bulan YYYY (kind)
        - ...
    """
    emp = conn.execute(
        "SELECT nama FROM employees WHERE id = ?", (employee_id,)
    ).fetchone()
    if not emp:
        return ""

    if year_month:
        from src.core.week_utils import full_month_range
        start, end = full_month_range(year_month)
        issues = conn.execute(
            """
            SELECT tanggal, hari, masuk, keluar
              FROM attendance_records
             WHERE employee_id = ? AND has_issue = 1 AND reason_category IS NULL
               AND tanggal BETWEEN ? AND ?
             ORDER BY tanggal
            """,
            (employee_id, start, end),
        ).fetchall()
    else:
        issues = conn.execute(
            """
            SELECT tanggal, hari, masuk, keluar
              FROM attendance_records
             WHERE employee_id = ? AND has_issue = 1 AND reason_category IS NULL
             ORDER BY tanggal
            """,
            (employee_id,),
        ).fetchall()

    if not issues:
        return ""

    lines = [f"{emp['nama']} ({len(issues)} issue)"]
    for r in issues:
        kind = _describe_kind(r["masuk"], r["keluar"])
        lines.append(f"- {r['hari']}, {_format_date_id(r['tanggal'])} ({kind})")
    return "\n".join(lines)
