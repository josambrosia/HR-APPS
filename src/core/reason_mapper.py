from typing import Optional

# Human-readable labels for UI
REASON_LABELS = {
    "tugas_lapangan":  "Tugas Lapangan",
    "tugas_paparan":   "Tugas Paparan",
    "izin_sakit":      "Izin Sakit",
    "cuti":            "Cuti",
    "terlambat_kerja": "Masuk Terlambat dengan Alasan Pekerjaan",
    "terlambat_lain":  "Terlambat dengan alasan",
    "lupa_absen":      "Lupa Absen",
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
