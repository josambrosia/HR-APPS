import pytest

from src.core.dinas_recap import (
    SPANS, DEFAULT_SPAN, resolve_range, span_label, rank)


def test_default_span_is_year():
    assert DEFAULT_SPAN == "year"
    assert [s[0] for s in SPANS] == ["3m", "6m", "year"]
    assert dict(SPANS)["year"] == "Tahun ini"


def test_year_span_is_full_calendar_year():
    assert resolve_range("2026-07", "year") == ("2026-01-01", "2026-12-31")
    assert resolve_range("2026-01", "year") == ("2026-01-01", "2026-12-31")


def test_3m_span_is_inclusive_backwards():
    # Juli 2026 -> Mei, Jun, Jul
    assert resolve_range("2026-07", "3m") == ("2026-05-01", "2026-07-31")


def test_6m_span_is_inclusive_backwards():
    # Juli 2026 -> Feb..Jul
    assert resolve_range("2026-07", "6m") == ("2026-02-01", "2026-07-31")


def test_span_crosses_year_boundary():
    # Februari 2026, 6 bulan -> September 2025 .. Februari 2026
    assert resolve_range("2026-02", "6m") == ("2025-09-01", "2026-02-28")
    # Januari 2026, 3 bulan -> November 2025 .. Januari 2026
    assert resolve_range("2026-01", "3m") == ("2025-11-01", "2026-01-31")


def test_end_day_follows_month_length():
    assert resolve_range("2026-02", "3m")[1] == "2026-02-28"
    assert resolve_range("2024-02", "3m")[1] == "2024-02-29"  # kabisat


def test_unknown_span_raises():
    with pytest.raises(KeyError):
        resolve_range("2026-07", "9m")


def test_span_label_same_year_omits_first_year():
    assert span_label("2026-07", "year") == "Januari – Desember 2026"
    assert span_label("2026-07", "3m") == "Mei – Juli 2026"


def test_span_label_cross_year_shows_both():
    assert span_label("2026-02", "6m") == "September 2025 – Februari 2026"


def test_rank_numbers_sequentially_and_copies():
    rows = [{"nama": "A", "total": 9}, {"nama": "B", "total": 4}]
    out = rank(rows)
    assert [r["rank"] for r in out] == [1, 2]
    assert "rank" not in rows[0]  # input tidak dimutasi


def test_rank_empty_list():
    assert rank([]) == []
