import re
from datetime import datetime
from typing import Optional, Union


def parse_decimal_id(value) -> Optional[float]:
    """Parse Indonesian-style decimal ('7,9') OR English ('7.9'). Return None on blank/garbage."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if not s:
        return None
    # If it looks like 'Libur' or non-numeric, return None
    cleaned = s.replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


_TIME_RE = re.compile(r"^(\d{1,2})\.(\d{2})$")


def parse_time_dot(value) -> Optional[str]:
    """Convert '08.06' → '08:06'. Return None for blank/non-time strings."""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    m = _TIME_RE.match(s)
    if not m:
        return None
    return f"{int(m.group(1)):02d}:{m.group(2)}"


def parse_date_id(value) -> Optional[str]:
    """Parse 'DD/MM/YYYY' or pass through ISO 'YYYY-MM-DD' or datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    s = str(value).strip()
    if not s:
        return None
    # Try DMY
    try:
        return datetime.strptime(s, "%d/%m/%Y").strftime("%Y-%m-%d")
    except ValueError:
        pass
    # Try ISO
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError:
        return None
