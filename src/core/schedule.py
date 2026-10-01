"""Pure helpers for schedule periods (v26). No I/O, no Tk."""
from datetime import date

from src.core.attendance_calc import to_minutes


def validate_period(effective_from: str, start: str, end: str) -> str | None:
    """Pesan error untuk input dialog jadwal, atau None bila valid."""
    try:
        date.fromisoformat(effective_from)
    except (TypeError, ValueError):
        return "Tanggal berlaku harus format YYYY-MM-DD."
    sm, em = to_minutes(start), to_minutes(end)
    if sm is None or em is None:
        return "Jam masuk/pulang harus format HH.MM (mis. 09.00)."
    if sm >= em:
        return "Jam masuk harus lebih awal dari jam pulang."
    return None


def is_future(effective_from: str) -> bool:
    """True bila periode belum berlaku (boleh dihapus saat salah input)."""
    try:
        return date.fromisoformat(effective_from) > date.today()
    except (TypeError, ValueError):
        return False
