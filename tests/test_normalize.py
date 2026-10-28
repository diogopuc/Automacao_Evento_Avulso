from datetime import date, time
from app.normalize import normalize_id, parse_date, parse_time

def test_normalization_keeps_leading_zeroes_and_parses_supported_values():
    assert normalize_id(" 000123 ") == "000123"
    assert parse_date("28/10/2026") == date(2026, 10, 28)
    assert parse_time("08:45") == time(8, 45)
