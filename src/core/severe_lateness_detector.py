# src/core/severe_lateness_detector.py
"""Pure predicate: is a single attendance row a 'severe lateness' day?

A severe-lateness day is a Hari Kerja where BOTH punches are present and the
recorded lateness meets/exceeds the threshold. Distinct from an Issue (which
requires a MISSING punch), so the two sets never overlap.
"""


def is_severe_lateness(row, threshold_min: int) -> bool:
    """row supports row["tipe"], row["masuk"], row["keluar"],
    row["terlambat_menit"] (dict or sqlite3.Row)."""
    if row["tipe"] != "Hari Kerja":
        return False
    if not row["masuk"] or not row["keluar"]:
        return False
    late = row["terlambat_menit"] or 0
    return late >= threshold_min
