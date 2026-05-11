from src.parsers.helpers import parse_decimal_id, parse_time_dot, parse_date_id


def test_parse_decimal_with_comma():
    assert parse_decimal_id("7,9") == 7.9
    assert parse_decimal_id("0,1") == 0.1


def test_parse_decimal_with_dot_also_works():
    assert parse_decimal_id("7.9") == 7.9


def test_parse_decimal_int_string():
    assert parse_decimal_id("8") == 8.0


def test_parse_decimal_blank_returns_none():
    assert parse_decimal_id("") is None
    assert parse_decimal_id(None) is None
    assert parse_decimal_id("  ") is None


def test_parse_decimal_garbage_returns_none():
    assert parse_decimal_id("Libur") is None
    assert parse_decimal_id("xyz") is None


def test_parse_time_dot():
    assert parse_time_dot("08.06") == "08:06"
    assert parse_time_dot("16.41") == "16:41"


def test_parse_time_dot_blank():
    assert parse_time_dot("") is None
    assert parse_time_dot(None) is None


def test_parse_time_dot_libur_treated_as_blank():
    """Real fingerprint exports sometimes contain 'Libur' text where time would go."""
    assert parse_time_dot("Libur") is None


def test_parse_date_dmy():
    assert parse_date_id("01/04/2026") == "2026-04-01"
    assert parse_date_id("30/04/2026") == "2026-04-30"


def test_parse_date_iso_passthrough():
    assert parse_date_id("2026-04-01") == "2026-04-01"


def test_parse_date_datetime_passthrough():
    from datetime import datetime
    assert parse_date_id(datetime(2026, 4, 1)) == "2026-04-01"
