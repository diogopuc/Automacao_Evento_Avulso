from datetime import date, time

from app.models import RequestRecord
from app.rest_rules import check_rest_rules


def record(day: date, start: time, end: time, identifier: str = "1") -> RequestRecord:
    return RequestRecord({}, "0001", day, start, end, f"{identifier}.xlsx", f"{identifier}.xlsx", "Solicitações", 2, "1. LETIVA", "p", identifier, "exec")


def test_intrajornada_requires_fifteen_minutes_for_five_to_six_hours():
    records = [record(date(2026, 10, 28), time(8), time(11)), record(date(2026, 10, 28), time(11, 10), time(13, 40), "2")]
    check_rest_rules(records, [])
    assert all(message.intrajornada_message.startswith("Não conforme") for message in records)
    assert "00:15" in records[0].intrajornada_message


def test_intrajornada_requires_one_hour_from_seven_hours():
    records = [record(date(2026, 10, 28), time(8), time(12)), record(date(2026, 10, 28), time(13), time(16, 30), "2")]
    check_rest_rules(records, [])
    assert records[0].intrajornada_message.startswith("Conforme")
    assert "01:00" in records[0].intrajornada_message


def test_intrajornada_flags_workday_above_eight_hours():
    item = record(date(2026, 10, 28), time(8), time(16, 30))
    check_rest_rules([item], [])
    assert item.intrajornada_message.startswith("Não conforme")
    assert "máximo de 08:00" in item.intrajornada_message


def test_interjornada_requires_eleven_hours_between_days():
    previous = record(date(2026, 10, 28), time(20), time(23))
    current = record(date(2026, 10, 29), time(9), time(10), "2")
    check_rest_rules([previous, current], [])
    assert current.interjornada_message.startswith("Não conforme")
    assert "10:00" in current.interjornada_message
