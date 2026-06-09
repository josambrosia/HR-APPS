"""Pure presentation logic for the attendance heatmap. cell_status() maps one
(employee, date) to a status key; the dicts give colour/code/label. Independent
of effective_attendance() (which is for export number adjustment) — the
reason-over-lateness precedence reproduces the same justified-late behaviour."""
from src.config import HEATMAP_DINAS_REASONS

# status_key -> hex / code / human label
STATUS_COLORS = {
    "hadir": "#10B981", "dinas": "#047857", "sedang": "#EC4899",
    "parah": "#BE185D", "sakit": "#22D3EE", "cuti": "#A855F7",
    "lupa": "#EAB308", "mangkir": "#DC2626", "na": "#DC2626",
    "libur": "#FFFFFF", "nodata": "#9CA3AF",
}
STATUS_CODES = {
    "hadir": "H", "dinas": "D", "sedang": "TR", "parah": "TB", "sakit": "S",
    "cuti": "C", "lupa": "LA", "mangkir": "X", "na": "NA", "libur": "·",
    "nodata": "–",
}
STATUS_LABELS = {
    "hadir": "Hadir tepat waktu",
    "dinas": "Dinas (lapangan/paparan/belajar/terlambat dengan alasan)",
    "sedang": "Terlambat Ringan", "parah": "Terlambat Berat",
    "sakit": "Izin Sakit", "cuti": "Cuti", "lupa": "Lupa absen",
    "mangkir": "Absen Tanpa Alasan", "na": "NA / belum ada kabar",
    "libur": "Libur / weekend", "nodata": "Belum ada data",
}
# statuses that count toward HK (hari kerja dihadiri)
HK_STATUSES = ("hadir", "sedang", "parah", "dinas", "lupa")
# leave/justified reasons whose colour overrides lateness (terlambat_lain NOT here)
_LEAVE_REASON_STATUS = {
    "izin_sakit": "sakit", "cuti": "cuti",
    "lupa_absen_datang": "lupa", "lupa_absen_pulang": "lupa",
    "na": "na", "libur": "libur",
}


def cell_status(row, *, tolerance, severe, is_weekend, is_holiday):
    """row is a dict-like attendance record or None. Returns a status key."""
    # 1. Libur
    if is_weekend or is_holiday or (row is not None and row["tipe"] == "Hari Libur"):
        return "libur"
    # 2. No data
    if row is None:
        return "nodata"
    reason = row["reason_category"]
    # 3. Leave/justified reason colour wins
    if reason in HEATMAP_DINAS_REASONS:
        return "dinas"
    if reason in _LEAVE_REASON_STATUS:
        return _LEAVE_REASON_STATUS[reason]
    # (terlambat_lain falls through to lateness tiers)
    # 4. Present + lateness tiers
    if row["masuk"]:
        late = row["terlambat_menit"] or 0
        if late <= tolerance:
            return "hadir"
        if late < severe:
            return "sedang"
        return "parah"
    # 5. Hari Kerja, no punch, no reason
    return "mangkir"
