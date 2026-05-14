"""Tests for fill_monthly_report dry_run + out_dir parameters."""
import pytest
from pathlib import Path
import shutil

from src.config import TEMPLATE_LAPORAN_BULANAN
from src.db.connection import get_connection
from src.db.schema import init_db
from src.core.report_filler import fill_monthly_report


@pytest.fixture
def setup_env(tmp_path):
    """Copy bundled template to tmp so we can mutate around it."""
    db_path = tmp_path / "test.db"
    init_db(db_path)
    template = tmp_path / "Laporan April.xlsx"
    shutil.copy(TEMPLATE_LAPORAN_BULANAN, template)
    return db_path, template, tmp_path


def test_dry_run_does_not_write_file(setup_env):
    db_path, template, tmp = setup_env
    before = set(tmp.iterdir())
    with get_connection(db_path) as conn:
        out_path, summary = fill_monthly_report(
            template, conn, dry_run=True,
        )
    after = set(tmp.iterdir())
    # No new file created
    assert before == after
    # Summary still returned
    assert summary is not None
    # out_path is the predicted name; not written to disk
    # (it should NOT exist OR be the unchanged template)
    if out_path != template:
        assert not out_path.exists()


def test_out_dir_redirects_save_location(setup_env):
    db_path, template, tmp = setup_env
    out_dir = tmp / "subdir"
    out_dir.mkdir()
    with get_connection(db_path) as conn:
        out_path, summary = fill_monthly_report(
            template, conn, dry_run=False, out_dir=out_dir,
        )
    assert out_path.parent == out_dir
    assert out_path.exists()


def test_fill_skips_holiday_rows(synthetic_monthly_xlsx, tmp_path):
    """A row whose DB tipe is 'Hari Libur' is skipped — column Q not written."""
    import sqlite3
    from src.db.schema import DDL
    from src.db.employees import upsert_employee
    from src.db.attendance import upsert_attendance
    from src.db.holidays import mark_holidays
    from src.core.report_filler import fill_monthly_report
    from openpyxl import load_workbook

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(DDL)
    budi = upsert_employee(conn, no_staff="9001", nama="BUDI", dept="TEST")
    upsert_attendance(
        conn, employee_id=budi, tanggal="2026-04-03", hari="Rabu",
        tipe="Hari Kerja", jadwal="08.00 - 16.00", masuk=None, keluar=None,
        kerja_jam=None, lembur_jam=None, terlambat_menit=None, has_issue=1,
        imported_from="t.xls",
    )
    mark_holidays(conn, ["2026-04-03"])
    out_path, _summary = fill_monthly_report(
        synthetic_monthly_xlsx, conn, dry_run=False, out_dir=tmp_path,
    )
    ws = load_workbook(out_path).active
    # synthetic_monthly_xlsx row 5 = BUDI 2026-04-03; column Q (17) stays blank
    assert ws.cell(row=5, column=17).value in (None, "")
