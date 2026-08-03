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


def rank_by(rows: List[dict], metric: str) -> List[dict]:
    """Papan peringkat SATU metrik ('dinas' atau 'paparan').

    Mengurutkan sendiri (metrik menurun, lalu nama) — jadi tidak bergantung
    pada urutan SQL yang dipakai panel bulanan.

    Menambahkan:
      value    — nilai metrik yang diperingkat (menyeragamkan render panel)
      bar_pct  — panjang bar relatif terhadap pemuncak METRIK ITU
      mark     — 👑 juara, 💎 peringkat 2-3; kosong bila nilainya 0, sebab
                 daftar memuat seluruh pegawai aktif termasuk yang nol.
    """
    ordered = sorted(rows, key=lambda r: (-r[metric], r["nama"]))
    ranked = rank(ordered)
    top = ranked[0][metric] if ranked else 0
    for r in ranked:
        r["value"] = r[metric]
        r["bar_pct"] = round(r[metric] / top * 100) if top else 0
        if r[metric] > 0 and r["rank"] <= 3:
            r["mark"] = "👑" if r["rank"] == 1 else "💎"
        else:
            r["mark"] = ""
    return ranked


def sort_month_rows(rows: List[dict], key: str, *, descending: bool = True) -> List[dict]:
    """Urutkan panel bulanan menurut kolom yang diklik.

    key 'nama' selalu alfabetis; kolom angka ('dinas'/'paparan'/'total')
    memakai nama sebagai pemecah seri agar urutannya deterministik.
    """
    if key == "nama":
        return sorted(rows, key=lambda r: r["nama"].lower(), reverse=descending)
    sign = -1 if descending else 1
    return sorted(rows, key=lambda r: (sign * r[key], r["nama"].lower()))


def decorate_ranks(rows: List[dict]) -> List[dict]:
    """rank() + bidang tampilan papan peringkat. Dipakai layar DAN cetakan agar
    keduanya tak pernah berbeda.

    Menambahkan:
      bar_pct     — panjang bar relatif terhadap pemuncak
      dinas_pct   — porsi dinas DI DALAM bar (dinas+paparan = 100)
      paparan_pct — sisanya
      mark        — 👑 juara, 💎 peringkat 2-3; kosong bila total 0, sebab
                    daftar memuat seluruh pegawai aktif termasuk yang nol.
    """
    ranked = rank(rows)
    top = ranked[0]["total"] if ranked else 0
    for r in ranked:
        r["bar_pct"] = round(r["total"] / top * 100) if top else 0
        r["dinas_pct"] = round(r["dinas"] / r["total"] * 100) if r["total"] else 0
        r["paparan_pct"] = 100 - r["dinas_pct"] if r["total"] else 0
        if r["total"] > 0 and r["rank"] <= 3:
            r["mark"] = "👑" if r["rank"] == 1 else "💎"
        else:
            r["mark"] = ""
    return ranked


def champion_of(ranked: List[dict]):
    """Pemuncak yang benar-benar bertugas, atau None."""
    return ranked[0] if ranked and ranked[0]["total"] > 0 else None
