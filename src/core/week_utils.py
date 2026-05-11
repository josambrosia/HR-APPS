"""Week-of-month helpers for the HR Absensi App.

Weeks are sequential within a calendar month: Minggu 1 = day 1-7,
Minggu 2 = day 8-14, etc. The final week may be shorter if the
month doesn't divide evenly. Aligned with how the user's fingerprint
exports tend to land.
"""
from calendar import monthrange
from datetime import date
from typing import List, Tuple


def parse_month(month_str: str) -> Tuple[int, int]:
    """Parse 'YYYY-MM' into (year, month). Raises ValueError on bad input."""
    year_s, month_s = month_str.split("-")
    return int(year_s), int(month_s)


def weeks_in_month(month_str: str) -> List[Tuple[int, str, str]]:
    """Return list of (week_num, start_iso, end_iso) tuples for the given YYYY-MM.

    Example for 2026-04 (April has 30 days):
      [(1, '2026-04-01', '2026-04-07'),
       (2, '2026-04-08', '2026-04-14'),
       (3, '2026-04-15', '2026-04-21'),
       (4, '2026-04-22', '2026-04-28'),
       (5, '2026-04-29', '2026-04-30')]
    """
    year, month = parse_month(month_str)
    last_day = monthrange(year, month)[1]
    weeks: List[Tuple[int, str, str]] = []
    start_day = 1
    week_num = 1
    while start_day <= last_day:
        end_day = min(start_day + 6, last_day)
        weeks.append((
            week_num,
            f"{year:04d}-{month:02d}-{start_day:02d}",
            f"{year:04d}-{month:02d}-{end_day:02d}",
        ))
        start_day += 7
        week_num += 1
    return weeks


def week_number_for(date_iso: str) -> int:
    """Given an ISO date string YYYY-MM-DD, return 1-based week-of-month number."""
    day = int(date_iso.split("-")[2])
    return ((day - 1) // 7) + 1


def full_month_range(month_str: str) -> Tuple[str, str]:
    """Return (first_day_iso, last_day_iso) for the whole month."""
    year, month = parse_month(month_str)
    last_day = monthrange(year, month)[1]
    return f"{year:04d}-{month:02d}-01", f"{year:04d}-{month:02d}-{last_day:02d}"
