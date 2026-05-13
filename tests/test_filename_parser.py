"""Tests for detect_year_month_from_filename."""
import pytest
from pathlib import Path
from src.core.filename_parser import detect_year_month_from_filename


def test_indonesian_full_month_name():
    assert detect_year_month_from_filename(
        Path("Laporan Bulanan April 2026.xlsx")
    ) == "2026-04"


def test_indonesian_short_month_name():
    assert detect_year_month_from_filename(
        Path("Laporan Apr 2026.xlsx")
    ) == "2026-04"


def test_iso_yyyy_mm_format():
    assert detect_year_month_from_filename(
        Path("report-2026-05.xlsx")
    ) == "2026-05"


def test_iso_underscore_format():
    assert detect_year_month_from_filename(
        Path("report_2026_03.xlsx")
    ) == "2026-03"


def test_returns_none_when_no_match():
    assert detect_year_month_from_filename(
        Path("random-file.xlsx")
    ) is None


def test_case_insensitive():
    assert detect_year_month_from_filename(
        Path("Laporan MARET 2026.xlsx")
    ) == "2026-03"


def test_iso_invalid_month_rejected():
    """Month 13+ or 00 not a valid match."""
    assert detect_year_month_from_filename(Path("report-2026-13.xlsx")) is None
    assert detect_year_month_from_filename(Path("report-2026-00.xlsx")) is None


def test_iso_with_day_component():
    """YYYY-MM-DD: still extracts month part."""
    assert detect_year_month_from_filename(Path("report-2026-08-15.xlsx")) == "2026-08"


def test_word_boundary_prevents_false_match():
    """Word-boundary regex prevents prefix substring matches."""
    # "augmentasi" should NOT match "aug"
    assert detect_year_month_from_filename(Path("augmentasi 2026.xlsx")) is None
