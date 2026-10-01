import sqlite3

import pytest

from src.core.schedule import is_future, validate_period
from src.db.connection import get_connection
from src.db.schedule import (add_period, current_schedule, delete_period,
                             list_periods, schedule_for)
from src.db.schema import init_db
from src.db.settings import get_setting


def test_fresh_db_has_single_new_period(tmp_path):
    p = tmp_path / "s.db"
    init_db(p)
    with get_connection(p) as conn:
        periods = list_periods(conn)
        assert len(periods) == 1
        assert periods[0]["effective_from"] == "1970-01-01"
        assert periods[0]["start_time"] == "09.00"
        assert periods[0]["end_time"] == "17.00"
        assert schedule_for(conn, "2026-01-01") == ("09.00", "17.00")


def test_legacy_then_cutover(tmp_path):
    p = tmp_path / "s.db"
    with sqlite3.connect(p) as conn:
        conn.execute("CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute("INSERT INTO settings VALUES ('schedule_start','08.00')")
        conn.execute("INSERT INTO settings VALUES ('schedule_end','16.00')")
        conn.commit()
    init_db(p)
    with get_connection(p) as conn:
        assert schedule_for(conn, "2026-09-13") == ("08.00", "16.00")
        assert schedule_for(conn, "2026-09-14") == ("09.00", "17.00")
        assert schedule_for(conn, "2025-01-01") == ("08.00", "16.00")


def test_add_period_mirrors_settings_and_affects_later_dates(tmp_path):
    p = tmp_path / "s.db"
    init_db(p)
    with get_connection(p) as conn:
        add_period(conn, effective_from="1970-01-02", start="10.00", end="18.00")
        assert schedule_for(conn, "1970-01-03") == ("10.00", "18.00")
        assert current_schedule(conn) == ("10.00", "18.00")
        assert get_setting(conn, "schedule_start") == "10.00"
        assert get_setting(conn, "schedule_end") == "18.00"


def test_add_period_duplicate_date_rejected(tmp_path):
    p = tmp_path / "s.db"
    init_db(p)
    with get_connection(p) as conn:
        with pytest.raises(sqlite3.IntegrityError):
            add_period(conn, effective_from="1970-01-01",
                       start="10.00", end="18.00")


def test_delete_period_restores_settings_mirror(tmp_path):
    p = tmp_path / "s.db"
    init_db(p)
    with get_connection(p) as conn:
        add_period(conn, effective_from="1970-01-02", start="10.00", end="18.00")
        periods = list_periods(conn)
        newest = periods[-1]["id"]
        delete_period(conn, newest)
        assert get_setting(conn, "schedule_start") == "09.00"
        assert get_setting(conn, "schedule_end") == "17.00"


def test_validate_period():
    assert validate_period("bukan-tanggal", "09.00", "17.00") is not None
    assert validate_period("2026-10-01", "17.00", "09.00") is not None
    assert validate_period("2026-10-01", "09.00", "09.00") is not None
    assert validate_period("2026-10-01", "x", "17.00") is not None
    assert validate_period("2026-10-01", "09.00", "17.00") is None


def test_is_future():
    assert is_future("2999-01-01") is True
    assert is_future("1970-01-01") is False
    assert is_future("bukan-tanggal") is False
