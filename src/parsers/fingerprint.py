from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
import warnings

import pandas as pd

from src.parsers.helpers import parse_decimal_id, parse_time_dot, parse_date_id


@dataclass
class FingerprintRow:
    nama: str
    no_staff: str
    dept: Optional[str]
    tanggal: str          # ISO YYYY-MM-DD
    hari: Optional[str]
    tipe: Optional[str]   # "Hari Kerja" | "Istirahat" | ...
    jadwal: Optional[str]
    masuk: Optional[str]  # HH:MM or None
    keluar: Optional[str]
    kerja_jam: Optional[float]
    lembur_jam: Optional[float]
    terlambat_menit: Optional[int]
    source_file: str


def _cell(value) -> Optional[str]:
    """Return None for NaN/blank cells, otherwise the stripped string value."""
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    s = str(value).strip()
    return s if s else None


def parse_fingerprint_file(path: Path) -> List[FingerprintRow]:
    """Parse a weekly fingerprint Excel file (.xls or .xlsx) into normalized rows."""
    # Suppress xlrd OLE2 warnings (mesin fingerprint quirk)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        df = pd.read_excel(path, header=0, skiprows=[1], dtype=str)

    rows: List[FingerprintRow] = []
    for _, r in df.iterrows():
        nama = _cell(r.get("Nama")) or ""
        if not nama or "Total" in nama:
            continue

        tanggal_iso = parse_date_id(_cell(r.get("Tanggal")))
        if not tanggal_iso:
            continue

        terlambat_raw = parse_decimal_id(_cell(r.get("Terlambat")))
        terlambat_int = int(terlambat_raw) if terlambat_raw is not None else None

        no_staff = _cell(r.get("No. Staff")) or ""
        dept = _cell(r.get("Dept."))
        hari = _cell(r.get("Hari"))
        tipe = _cell(r.get("Tipe"))
        jadwal = _cell(r.get("Jadwal"))

        rows.append(
            FingerprintRow(
                nama=nama,
                no_staff=no_staff,
                dept=dept,
                tanggal=tanggal_iso,
                hari=hari,
                tipe=tipe,
                jadwal=jadwal,
                masuk=parse_time_dot(_cell(r.get("Masuk"))),
                keluar=parse_time_dot(_cell(r.get("Keluar"))),
                kerja_jam=parse_decimal_id(_cell(r.get("Kerja"))),
                lembur_jam=parse_decimal_id(_cell(r.get("Lembur"))),
                terlambat_menit=terlambat_int,
                source_file=path.name,
            )
        )
    return rows
