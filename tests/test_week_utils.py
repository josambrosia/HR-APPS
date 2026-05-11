from src.core.week_utils import weeks_in_month, week_number_for, full_month_range


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
