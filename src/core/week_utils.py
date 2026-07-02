"""Week-of-month helpers for the HR Absensi App.

Weeks are Monday-to-Sunday. The first week of a month begins on day 1
(possibly a partial week — e.g., if the month starts on Wednesday, week 1
spans Wed-Sun). Subsequent weeks start on Monday and end on Sunday. The
final week may also be partial.

This matches the user's HR workflow: weekly fingerprint cycles align with
the standard Mon-Sun work week, not arbitrary day-1-as-week-1 chunks.

This module is also the canonical home for:
- MONTH_NAMES_ID — Indonesian month names shared by screens and reports.
- parse_week_key / week_range / resolve_period — the week-nav key
  ('semua' / 'minggu_N') → date-range resolution shared by the Dashboard,
  Issues, Severe Lateness and Coaching screens.
"""
from calendar import monthrange
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

# Indonesian month names keyed by month number (1-12). Single source of
# truth — screens and report modules should use this instead of local
# copies. Kept as a dict (not a 0-padded list) so out-of-range lookups
# raise KeyError, which existing formatters already catch.
MONTH_NAMES_ID: Dict[int, str] = {
    1: "Januari", 2: "Februari", 3: "Maret", 4: "April",
    5: "Mei", 6: "Juni", 7: "Juli", 8: "Agustus",
    9: "September", 10: "Oktober", 11: "November", 12: "Desember",
}


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


def parse_week_key(week_key: str) -> Optional[int]:
    """Parse a week-nav key like 'minggu_3' into its week number (3).

    Returns None when no number can be extracted — e.g. 'semua' or a
    malformed key. Callers decide their own fallback (full month, week 1,
    ...), so this helper stays judgment-free.
    """
    try:
        return int(week_key.split("_")[1])
    except (IndexError, ValueError):
        return None


def week_range(month_str: str, week_num: int) -> Optional[Tuple[str, str]]:
    """Return (start_iso, end_iso) for the given week of a YYYY-MM month.

    Returns None when the month has no such week (e.g. week 6 of a
    five-week month), leaving the fallback choice to the caller.
    """
    for num, start, end in weeks_in_month(month_str):
        if num == week_num:
            return start, end
    return None


def resolve_period(
    month_str: str, week_key: str, default_week: Optional[int] = None,
) -> Tuple[str, str, Optional[int]]:
    """Resolve a week-nav key against a YYYY-MM month into a date range.

    Key semantics (shared by the Dashboard / Issues / Severe Lateness
    period helpers):
      - 'semua'                     → the full month
      - 'minggu_N' and week exists  → that week's range
      - 'minggu_N' but no such week → the full month
      - malformed key               → week `default_week` when given
                                      (Dashboard behavior), else the
                                      full month (Issues behavior)

    Returns (start_iso, end_iso, week_num) where week_num is the matched
    week number, or None when the range is the whole month — callers use
    it to build a "Bulanan" vs "Minggu N" label.
    """
    if week_key != "semua":
        num = parse_week_key(week_key)
        if num is None:
            num = default_week
        if num is not None:
            rng = week_range(month_str, num)
            if rng is not None:
                return rng[0], rng[1], num
    start, end = full_month_range(month_str)
    return start, end, None
