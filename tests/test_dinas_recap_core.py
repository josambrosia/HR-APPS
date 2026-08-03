import pytest

from src.core.dinas_recap import (
    SPANS, DEFAULT_SPAN, resolve_range, span_label, rank, rank_by,
    sort_month_rows)


def _rows():
    return [
        {"nama": "Andi", "dinas": 2, "paparan": 5, "total": 7},
        {"nama": "Budi", "dinas": 6, "paparan": 0, "total": 6},
        {"nama": "Cici", "dinas": 0, "paparan": 0, "total": 0},
    ]


# ---- rank_by: papan peringkat satu metrik ----

def test_rank_by_orders_by_its_own_metric():
    out = rank_by(_rows(), "dinas")
    assert [r["nama"] for r in out] == ["Budi", "Andi", "Cici"]
    assert [r["value"] for r in out] == [6, 2, 0]


def test_rank_by_paparan_differs_from_dinas():
    assert [r["nama"] for r in rank_by(_rows(), "paparan")] == ["Andi", "Budi", "Cici"]


def test_rank_by_bar_pct_relative_to_that_metric_top():
    out = rank_by(_rows(), "dinas")
    assert out[0]["bar_pct"] == 100          # Budi 6/6
    assert out[1]["bar_pct"] == 33           # Andi 2/6
    assert out[2]["bar_pct"] == 0


def test_rank_by_marks_only_nonzero_top3():
    out = rank_by(_rows(), "dinas")
    assert out[0]["mark"] == "👑"
    assert out[1]["mark"] == "💎"
    assert out[2]["mark"] == ""              # nilainya 0 — tanpa penanda


def test_rank_by_all_zero_gives_no_marks_and_no_bars():
    zeros = [{"nama": "A", "dinas": 0, "paparan": 0, "total": 0},
             {"nama": "B", "dinas": 0, "paparan": 0, "total": 0}]
    out = rank_by(zeros, "dinas")
    assert all(r["mark"] == "" and r["bar_pct"] == 0 for r in out)


def test_rank_by_does_not_mutate_input():
    rows = _rows()
    rank_by(rows, "dinas")
    assert "rank" not in rows[0] and "value" not in rows[0]


def test_rank_by_ties_break_on_name():
    tied = [{"nama": "Zulu", "dinas": 3, "paparan": 0, "total": 3},
            {"nama": "Alfa", "dinas": 3, "paparan": 0, "total": 3}]
    assert [r["nama"] for r in rank_by(tied, "dinas")] == ["Alfa", "Zulu"]


# ---- sort_month_rows: klik judul kolom ----

def test_sort_by_numeric_column_descending_then_ascending():
    assert [r["nama"] for r in sort_month_rows(_rows(), "dinas")] == \
        ["Budi", "Andi", "Cici"]
    assert [r["nama"] for r in sort_month_rows(_rows(), "dinas", descending=False)] == \
        ["Cici", "Andi", "Budi"]


def test_sort_by_name_is_alphabetical_both_ways():
    assert [r["nama"] for r in sort_month_rows(_rows(), "nama", descending=False)] == \
        ["Andi", "Budi", "Cici"]
    assert [r["nama"] for r in sort_month_rows(_rows(), "nama", descending=True)] == \
        ["Cici", "Budi", "Andi"]


def test_sort_numeric_ties_break_on_name():
    tied = [{"nama": "Zulu", "dinas": 1, "paparan": 0, "total": 1},
            {"nama": "Alfa", "dinas": 1, "paparan": 0, "total": 1}]
    assert [r["nama"] for r in sort_month_rows(tied, "dinas")] == ["Alfa", "Zulu"]


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
