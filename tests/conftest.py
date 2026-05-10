import pytest
from pathlib import Path
import pandas as pd
from openpyxl import Workbook


@pytest.fixture
def synthetic_fingerprint_xls(tmp_path: Path) -> Path:
    """Mini .xlsx fixture mimicking real fingerprint export structure."""
    rows = [
        # header row
        ["Nama", "No. Staff", "Dept.", "Tanggal", "Hari", "Tipe", "Jadwal",
         "", "Masuk", "", "Keluar", "Lembur Masuk", "Lembur Keluar",
         "Kerja", "Lembur", "Kurang", "Terlambat", "Pulang Cepat",
         "Absen", "Lupa in/out", "Ijin", "Alasan Ijin"],
        # sub-unit row (skipped on import)
        ["", "", "", "", "", "", "", "", "", "", "", "", "",
         "Jam", "Jam", "Jam", "Menit", "Menit", "Hari", "Hari", "Hari", ""],
        # data: BUDI Mon — clean
        ["BUDI", "9001", "TEST", "01/04/2026", "Senin", "Hari Kerja", "08.00 - 16.00",
         "", "08.05", "", "16.30", "", "", "7,9", "", "0,1", "5", "", "", "", "", ""],
        # data: BUDI Tue — lupa keluar (issue: keluar kosong)
        ["BUDI", "9001", "TEST", "02/04/2026", "Selasa", "Hari Kerja", "08.00 - 16.00",
         "", "08.10", "", "", "", "", "", "", "", "10", "", "", "1", "", ""],
        # data: BUDI Wed — tidak masuk (issue: keduanya kosong)
        ["BUDI", "9001", "TEST", "03/04/2026", "Rabu", "Hari Kerja", "08.00 - 16.00",
         "", "", "", "", "", "", "", "", "8", "", "", "1", "", "", ""],
        # data: BUDI Sat — istirahat (NOT issue)
        ["BUDI", "9001", "TEST", "05/04/2026", "Sabtu", "Istirahat", "",
         "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
        # ANI Mon — clean
        ["ANI", "9002", "TEST", "01/04/2026", "Senin", "Hari Kerja", "08.00 - 16.00",
         "", "07.58", "", "16.05", "", "", "8", "", "", "", "", "", "", "", ""],
        # Total row (must be filtered out on parse)
        ["Total Personal:", "", "", "", "", "", "", "", "", "", "", "", "",
         "15,9", "", "0,1", "15", "", "1", "1", "", ""],
    ]
    df = pd.DataFrame(rows[1:], columns=rows[0])
    # xlrd reads .xls (BIFF) — writing BIFF needs xlwt which is heavy.
    # We write .xlsx instead; the parser uses pandas.read_excel which
    # auto-detects engine, so it handles both .xls and .xlsx in production.
    out = tmp_path / "fingerprint_w1.xlsx"
    df.to_excel(out, index=False, header=True)
    return out


@pytest.fixture
def synthetic_monthly_xlsx(tmp_path: Path) -> Path:
    """Mini Laporan Bulanan with empty Alasan Ijin column."""
    wb = Workbook()
    ws = wb.active
    headers = ["Nama", "Dept.", "Tanggal", "Hari", "Tipe", "Jadwal",
               "Masuk", "Keluar", "Kerja", "Lembur", "Kurang",
               "Terlambat", "Pulang Cepat", "Absen", "Lupa in/out",
               "Ijin", "Alasan Ijin"]
    ws.append(headers)
    ws.append(["", "", "", "", "", "", "", "", "Jam", "Jam", "Jam",
               "Menit", "Menit", "Hari", "Hari", "Hari", ""])
    # rows
    ws.append(["BUDI", "TEST", "2026-04-01", "Senin", "Hari Kerja", "08.00 - 16.00",
               "08.05", "16.30", 7.9, None, 0.1, 5, None, None, None, None, None])
    ws.append(["BUDI", "TEST", "2026-04-02", "Selasa", "Hari Kerja", "08.00 - 16.00",
               "08.10", None, None, None, None, 10, None, None, 1, None, None])
    ws.append(["BUDI", "TEST", "2026-04-03", "Rabu", "Hari Kerja", "08.00 - 16.00",
               None, None, None, None, 8, None, None, 1, None, None, None])
    out = tmp_path / "laporan.xlsx"
    wb.save(out)
    return out


@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    return tmp_path / "test_hr.db"
