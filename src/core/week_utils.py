"""Week-of-month helpers for the HR Absensi App.

Weeks are Monday-to-Sunday. The first week of a month begins on day 1
(possibly a partial week — e.g., if the month starts on Wednesday, week 1
spans Wed-Sun). Subsequent weeks start on Monday and end on Sunday. The
final week may also be partial.

This matches the user's HR workflow: weekly fingerprint cycles align with
the standard Mon-Sun work week, not arbitrary day-1-as-week-1 chunks.
"""
from calendar import monthrange
from datetime import date, timedelta
from typing import List, Tuple


def parse_month(month_str: str) -> Tuple[int, int]:
    """Parse 'YYYY-MM' into (year, month). Raises ValueError on bad input."""
    year_s, month_s = month_str.split("-")
    return int(year_s), int(month_s)


def weeks_in_month(month_str: str) -> List[Tuple[int, str, str]]:
    """Return list of (week_num, start_iso, end_iso) for the given YYYY-MM.

    Weeks bounded by Mondays (start) and Sundays (end). First and last
    weeks may be partial. Example for April 2026 (Apr 1 = Wednesday):
      [(1, '2026-04-01', '2026-04-05'),  # Wed-Sun (partial)
       (2, '2026-04-06', '2026-04-12'),  # Mon-Sun
       (3, '2026-04-13', '2026-04-19'),
       (4, '2026-04-20', '2026-04-26'),
       (5, '2026-04-27', '2026-04-30')]  # Mon-Thu (partial)
    """
    year, month = parse_month(month_str)
    last_day_num = monthrange(year, month)[1]
    last = date(year, month, last_day_num)
    weeks: List[Tuple[int, str, str]] = []
    current = date(year, month, 1)
    week_num = 1
    while current <= last:
        # weekday(): Monday=0 ... Sunday=6
        days_until_sunday = 6 - current.weekday()
        end_of_week = current + timedelta(days=days_until_sunday)
        if end_of_week > last:
            end_of_week = last
        weeks.append((week_num, current.isoformat(), end_of_week.isoformat()))
        current = end_of_week + timedelta(days=1)
        week_num += 1
    return weeks


def week_number_for(date_iso: str) -> int:
    """Given an ISO date string YYYY-MM-DD, return 1-based week-of-month using Mon-Sun weeks."""
    d = date.fromisoformat(date_iso)
    month_str = f"{d.year:04d}-{d.month:02d}"
    for num, start, end in weeks_in_month(month_str):
        if start <= date_iso <= end:
            return num
    return 0


def full_month_range(month_str: str) -> Tuple[str, str]:
    """Return (first_day_iso, last_day_iso) for the whole month."""
    year, month = parse_month(month_str)
    last_day = monthrange(year, month)[1]
    return f"{year:04d}-{month:02d}-01", f"{year:04d}-{month:02d}-{last_day:02d}"
