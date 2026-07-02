from src.core.week_utils import (
    MONTH_NAMES_ID,
    full_month_range,
    parse_week_key,
    resolve_period,
    week_number_for,
    week_range,
    weeks_in_month,
)


def test_weeks_in_april_2026():
    # April 2026: Apr 1 = Wednesday.
    # Mon-Sun weeks (with partials at start + end):
    weeks = weeks_in_month("2026-04")
    assert len(weeks) == 5
    assert weeks[0] == (1, "2026-04-01", "2026-04-05")   # Wed-Sun (partial)
    assert weeks[1] == (2, "2026-04-06", "2026-04-12")   # Mon-Sun
    assert weeks[2] == (3, "2026-04-13", "2026-04-19")
    assert weeks[3] == (4, "2026-04-20", "2026-04-26")
    assert weeks[4] == (5, "2026-04-27", "2026-04-30")   # Mon-Thu (partial)


def test_weeks_in_february_2026():
    # Feb 2026: Feb 1 = Sunday, last day = Feb 28 (Sat).
    weeks = weeks_in_month("2026-02")
    assert len(weeks) == 5
    assert weeks[0] == (1, "2026-02-01", "2026-02-01")   # Sun only
    assert weeks[1] == (2, "2026-02-02", "2026-02-08")
    assert weeks[-1] == (5, "2026-02-23", "2026-02-28")  # Mon-Sat (partial)


def test_weeks_in_january_2026():
    # Jan 2026: Jan 1 = Thursday, last day = Jan 31 (Sat).
    weeks = weeks_in_month("2026-01")
    assert len(weeks) == 5
    assert weeks[0] == (1, "2026-01-01", "2026-01-04")   # Thu-Sun (partial)
    assert weeks[-1] == (5, "2026-01-26", "2026-01-31")  # Mon-Sat (partial)


def test_week_number_for():
    # April 2026 mapping (see test_weeks_in_april_2026)
    assert week_number_for("2026-04-01") == 1
    assert week_number_for("2026-04-05") == 1
    assert week_number_for("2026-04-06") == 2
    assert week_number_for("2026-04-12") == 2
    assert week_number_for("2026-04-13") == 3
    assert week_number_for("2026-04-30") == 5


def test_full_month_range():
    assert full_month_range("2026-04") == ("2026-04-01", "2026-04-30")
    assert full_month_range("2026-02") == ("2026-02-01", "2026-02-28")


def test_parse_week_key_valid():
    assert parse_week_key("minggu_1") == 1
    assert parse_week_key("minggu_5") == 5
    assert parse_week_key("minggu_02") == 2   # int() tolerates leading zero
    assert parse_week_key("minggu_0") == 0    # parseable — existence checked later


def test_parse_week_key_unparseable():
    assert parse_week_key("semua") is None
    assert parse_week_key("minggu_x") is None
    assert parse_week_key("garbage") is None
    assert parse_week_key("") is None


def test_week_range_april_2026():
    assert week_range("2026-04", 1) == ("2026-04-01", "2026-04-05")
    assert week_range("2026-04", 3) == ("2026-04-13", "2026-04-19")
    assert week_range("2026-04", 5) == ("2026-04-27", "2026-04-30")


def test_week_range_missing_week_returns_none():
    assert week_range("2026-04", 6) is None   # April 2026 has 5 weeks
    assert week_range("2026-04", 0) is None
    assert week_range("2026-02", 6) is None   # Feb 2026 has 5 weeks


def test_week_range_six_week_month():
    # March 2026: Mar 1 = Sunday → week 1 is a single day and the month
    # stretches to six Mon-Sun weeks.
    assert week_range("2026-03", 1) == ("2026-03-01", "2026-03-01")
    assert week_range("2026-03", 6) == ("2026-03-30", "2026-03-31")


def test_week_range_leap_february():
    # Feb 2028 (leap): Feb 1 = Tuesday, last day = Feb 29 (Tue).
    assert week_range("2028-02", 1) == ("2028-02-01", "2028-02-06")
    assert week_range("2028-02", 5) == ("2028-02-28", "2028-02-29")
    assert week_range("2028-02", 6) is None


def test_resolve_period_semua_gives_full_month():
    assert resolve_period("2026-04", "semua") == ("2026-04-01", "2026-04-30", None)
    assert resolve_period("2026-02", "semua") == ("2026-02-01", "2026-02-28", None)
    assert resolve_period("2028-02", "semua") == ("2028-02-01", "2028-02-29", None)


def test_resolve_period_existing_week():
    assert resolve_period("2026-04", "minggu_2") == ("2026-04-06", "2026-04-12", 2)
    assert resolve_period("2026-02", "minggu_5") == ("2026-02-23", "2026-02-28", 5)
    assert resolve_period("2026-03", "minggu_6") == ("2026-03-30", "2026-03-31", 6)


def test_resolve_period_missing_week_falls_back_to_month():
    # Week 6 does not exist in April 2026 → whole month, week_num None.
    assert resolve_period("2026-04", "minggu_6") == ("2026-04-01", "2026-04-30", None)
    # Parseable-but-nonexistent week 0 also falls back — default_week only
    # applies to keys with no parseable number at all.
    assert resolve_period("2026-04", "minggu_0", default_week=1) == (
        "2026-04-01", "2026-04-30", None)


def test_resolve_period_malformed_key_without_default():
    # Issues / Severe Lateness behavior: malformed key → whole month.
    assert resolve_period("2026-04", "garbage") == ("2026-04-01", "2026-04-30", None)
    assert resolve_period("2026-04", "minggu_x") == ("2026-04-01", "2026-04-30", None)


def test_resolve_period_malformed_key_with_default_week():
    # Dashboard behavior: malformed key → week 1.
    assert resolve_period("2026-04", "garbage", default_week=1) == (
        "2026-04-01", "2026-04-05", 1)
    assert resolve_period("2026-04", "minggu_x", default_week=1) == (
        "2026-04-01", "2026-04-05", 1)


def test_month_names_id_complete():
    assert set(MONTH_NAMES_ID) == set(range(1, 13))
    assert MONTH_NAMES_ID[1] == "Januari"
    assert MONTH_NAMES_ID[8] == "Agustus"
    assert MONTH_NAMES_ID[12] == "Desember"
