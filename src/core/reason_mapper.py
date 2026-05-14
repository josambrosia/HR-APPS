from typing import Optional

from src.config import COACHING_EXCLUDED

# Human-readable labels for UI
REASON_LABELS = {
    "tugas_lapangan":  "Tugas Lapangan",
    "tugas_paparan":   "Tugas Paparan",
    "izin_sakit":      "Izin Sakit",
    "cuti":            "Cuti",
    "tugas_belajar":   "Tugas Belajar/Kuliah",
    "terlambat_kerja": "Masuk Terlambat dengan Alasan Pekerjaan",
    "terlambat_lain":  "Terlambat dengan alasan",
    "lupa_absen":      "Lupa Absen",
    "libur":           "Libur",
    "na":              "NA / Belum ada kabar",
}

# Categories that NEED a detail field
REASON_NEEDS_DETAIL = {"tugas_lapangan", "tugas_paparan", "terlambat_kerja", "terlambat_lain"}


def render_alasan_ijin(category: str, detail: Optional[str]) -> str:
    """Render the value to write into the Alasan Ijin column."""
    if category not in REASON_LABELS:
        raise ValueError(f"Unknown reason category: {category}")
    if category == "tugas_lapangan":
        return f"Tugas Lapangan di {detail or '-'}"
    if category == "tugas_paparan":
        return f"Tugas Paparan di {detail or '-'}"
    if category == "terlambat_kerja":
        return f"Masuk Terlambat dengan Alasan Pekerjaan: {detail or '-'}"
    if category == "terlambat_lain":
        return f"Terlambat dengan alasan: {detail or '-'}"
    return REASON_LABELS[category]


def _schedule_start_minutes(schedule_start: str) -> int:
    """Parse the schedule_start setting ('08.00' dot-format) to
    minutes-from-midnight. Falls back to 480 (08:00) on malformed input."""
    try:
        h, m = schedule_start.replace(":", ".").split(".")
        return int(h) * 60 + int(m)
    except (ValueError, AttributeError):
        return 8 * 60


def _minutes_to_hhmm(total_min: int) -> str:
    """480 -> '08:00', 495 -> '08:15'. Colon format, to match the masuk column."""
    h, m = divmod(total_min, 60)
    return f"{h:02d}:{m:02d}"


def effective_attendance(row, *, schedule_start: str, lupa_penalty_min: int) -> dict:
    """Compute the 'effective' Masuk & Terlambat for one attendance row,
    derived from reason_category. Does NOT touch the DB — used at export
    render time so the raw fingerprint columns stay intact.

    `row` must support row["reason_category"], row["masuk"], row["keluar"],
    row["terlambat_menit"] (works for both dict and sqlite3.Row).

    Returns {"masuk": str | None, "terlambat_menit": int | None}.

    Rules:
      - reason_category in COACHING_EXCLUDED (work-justified-late) AND raw
        masuk is set (a real late clock-in) -> masuk = schedule_start,
        terlambat_menit = 0.
      - reason_category in COACHING_EXCLUDED AND raw masuk is NULL (a no-badge
        field day) -> no correction; stays a justified absence.
      - reason_category == 'lupa_absen' AND masuk is NULL AND keluar is set
        (forgot to clock IN) -> terlambat_menit = lupa_penalty_min,
        masuk = schedule_start + lupa_penalty_min.
      - everything else (incl. lupa_absen forgot-OUT, other categories,
        no reason) -> raw values unchanged.
    """
    cat = row["reason_category"]
    masuk = row["masuk"]
    keluar = row["keluar"]
    terlambat = row["terlambat_menit"]

    if cat in COACHING_EXCLUDED:
        if masuk is not None:
            return {
                "masuk": _minutes_to_hhmm(_schedule_start_minutes(schedule_start)),
                "terlambat_menit": 0,
            }
        return {"masuk": masuk, "terlambat_menit": terlambat}

    if cat == "lupa_absen" and masuk is None and keluar is not None:
        return {
            "masuk": _minutes_to_hhmm(
                _schedule_start_minutes(schedule_start) + lupa_penalty_min),
            "terlambat_menit": lupa_penalty_min,
        }

    return {"masuk": masuk, "terlambat_menit": terlambat}
