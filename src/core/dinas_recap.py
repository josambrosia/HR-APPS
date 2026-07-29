"""Rentang & peringkat untuk layar Rekap Dinas — logika murni (tanpa DB/Tk).

Rentang papan peringkat: "Tahun ini" (Jan–Des tahun bulan terpilih, default)
atau 3/6 bulan terakhir yang dihitung MUNDUR dan INKLUSIF dari bulan terpilih.
Lihat docs/superpowers/specs/2026-07-30-reason-editing-dinas-paparan-recap-design.md.
"""
from calendar import monthrange
from typing import Dict, List, Tuple

from src.core.week_utils import MONTH_NAMES_ID

# (id, label) — urutan tampil pada segmented control.
SPANS: Tuple[Tuple[str, str], ...] = (
    ("3m", "3 bln"),
    ("6m", "6 bln"),
    ("year", "Tahun ini"),
)
DEFAULT_SPAN = "year"

# Berapa bulan mundur dari bulan terpilih (0 = bulan terpilih saja).
_MONTHS_BACK: Dict[str, int] = {"3m": 2, "6m": 5}


def resolve_range(year_month: str, span: str) -> Tuple[str, str]:
    """('YYYY-MM', span) -> (start_iso, end_iso), keduanya inklusif.

    span 'year' -> 1 Jan .. 31 Des tahun `year_month`.
    span '3m'/'6m' -> awal bulan (m-2 / m-5) .. akhir bulan terpilih.
    Melempar KeyError untuk span tak dikenal.
    """
    y, m = int(year_month[:4]), int(year_month[5:7])
    if span == "year":
        return f"{y:04d}-01-01", f"{y:04d}-12-31"
    back = _MONTHS_BACK[span]
    sy, sm = y, m - back
    while sm < 1:
        sm += 12
        sy -= 1
    last = monthrange(y, m)[1]
    return f"{sy:04d}-{sm:02d}-01", f"{y:04d}-{m:02d}-{last:02d}"


def span_label(year_month: str, span: str) -> str:
    """Label rentang untuk header layar & cetak, mis. 'Mei – Juli 2026'.
    Tahun awal ditulis hanya bila rentangnya melintasi tahun."""
    start, end = resolve_range(year_month, span)
    sy, sm = int(start[:4]), int(start[5:7])
    ey, em = int(end[:4]), int(end[5:7])
    if sy == ey:
        return f"{MONTH_NAMES_ID[sm]} – {MONTH_NAMES_ID[em]} {ey}"
    return f"{MONTH_NAMES_ID[sm]} {sy} – {MONTH_NAMES_ID[em]} {ey}"


def rank(rows: List[dict]) -> List[dict]:
    """Beri nomor peringkat 1..N pada baris yang SUDAH terurut dari SQL.
    Mengembalikan salinan dangkal — input tidak dimutasi."""
    return [{**r, "rank": i} for i, r in enumerate(rows, start=1)]
