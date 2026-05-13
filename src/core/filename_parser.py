"""Detect YYYY-MM from filenames containing month names or ISO codes."""
import re
from pathlib import Path


_MONTH_NAMES = {
    "januari": 1, "jan": 1,
    "februari": 2, "february": 2, "feb": 2,
    "maret": 3, "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "mei": 5, "may": 5,
    "juni": 6, "june": 6, "jun": 6,
    "juli": 7, "july": 7, "jul": 7,
    "agustus": 8, "august": 8, "ags": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "oktober": 10, "october": 10, "okt": 10, "oct": 10,
    "november": 11, "nov": 11,
    "desember": 12, "december": 12, "des": 12, "dec": 12,
}


def detect_year_month_from_filename(path: Path) -> str | None:
    """Parse filename for Indonesian/English month + year.

    Returns 'YYYY-MM' or None if no match.

    Recognized patterns:
        "Laporan Bulanan April 2026.xlsx" -> "2026-04"
        "Laporan Apr 2026 [filled].xlsx" -> "2026-04"
        "report-2026-05.xlsx" -> "2026-05"
        "report_2026_03.xlsx" -> "2026-03"
    """
    name = path.stem.lower()

    # Try ISO 'YYYY-MM' or 'YYYY_MM' first (more specific).
    # ISO 'YYYY-MM' or 'YYYY_MM'. Negative lookahead `(?!\d)` prevents matching
    # the YYYY-MM-DD pattern's month-day boundary (e.g. "2026-08-15" would
    # otherwise return "2026-08" which is correct but accidental).
    # Month must be 01-12 — month 13+ or 00 rejected.
    iso_match = re.search(r"(20\d{2})[-_](0[1-9]|1[0-2])(?!\d)", name)
    if iso_match:
        return f"{iso_match.group(1)}-{iso_match.group(2)}"

    # Sort month names by length DESC so "september" matches before "sep"
    sorted_months = sorted(_MONTH_NAMES.items(), key=lambda x: -len(x[0]))
    for word, month_num in sorted_months:
        # Match whole-word boundary
        if re.search(rf"\b{re.escape(word)}\b", name):
            year_match = re.search(r"\b(20\d{2})\b", name)
            if year_match:
                return f"{year_match.group(1)}-{month_num:02d}"

    return None
