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
