from src.core.week_utils import weeks_in_month, week_number_for, full_month_range


def test_weeks_in_april_2026():
    weeks = weeks_in_month("2026-04")
    # 30 days → 5 weeks: 1-7, 8-14, 15-21, 22-28, 29-30
    assert len(weeks) == 5
    assert weeks[0] == (1, "2026-04-01", "2026-04-07")
    assert weeks[1] == (2, "2026-04-08", "2026-04-14")
    assert weeks[2] == (3, "2026-04-15", "2026-04-21")
    assert weeks[3] == (4, "2026-04-22", "2026-04-28")
    assert weeks[4] == (5, "2026-04-29", "2026-04-30")


def test_weeks_in_february_2026():
    # 28 days → 4 even weeks
    weeks = weeks_in_month("2026-02")
    assert len(weeks) == 4
    assert weeks[-1] == (4, "2026-02-22", "2026-02-28")


def test_weeks_in_january_2026():
    # 31 days → 5 weeks, last = 29-31
    weeks = weeks_in_month("2026-01")
    assert len(weeks) == 5
    assert weeks[-1] == (5, "2026-01-29", "2026-01-31")


def test_week_number_for():
    assert week_number_for("2026-04-01") == 1
    assert week_number_for("2026-04-07") == 1
    assert week_number_for("2026-04-08") == 2
    assert week_number_for("2026-04-14") == 2
    assert week_number_for("2026-04-15") == 3
    assert week_number_for("2026-04-30") == 5


def test_full_month_range():
    assert full_month_range("2026-04") == ("2026-04-01", "2026-04-30")
    assert full_month_range("2026-02") == ("2026-02-01", "2026-02-28")
