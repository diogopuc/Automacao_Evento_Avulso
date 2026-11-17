from datetime import date, time

from app.models import Coverage, RequestRecord
from app.rest_rules import check_rest_rules


def record(day: date, start: time, end: time, identifier: str = "1") -> RequestRecord:
    return RequestRecord({}, "0001", day, start, end, identifier)


def test_intrajornada_requires_fifteen_minutes_for_five_to_six_hours():
    records = [record(date(2026, 10, 28), time(8), time(11)), record(date(2026, 10, 28), time(11, 10), time(13, 40), "2")]
    check_rest_rules(records, [], Coverage(True, date(2026, 10, 1), date(2026, 10, 31)))
    assert all(message.intrajornada_message.startswith("Não conforme") for message in records)
    assert "00:15" in records[0].intrajornada_message


def test_intrajornada_requires_one_hour_from_seven_hours():
    records = [record(date(2026, 10, 28), time(8), time(12)), record(date(2026, 10, 28), time(13), time(16, 30), "2")]
    check_rest_rules(records, [], Coverage(True, date(2026, 10, 1), date(2026, 10, 31)))
    assert records[0].intrajornada_message.startswith("Conforme")
    assert "01:00" in records[0].intrajornada_message


def test_intrajornada_flags_workday_above_eight_hours():
    item = record(date(2026, 10, 28), time(8), time(16, 30))
    check_rest_rules([item], [], Coverage(True, date(2026, 10, 1), date(2026, 10, 31)))
    assert item.intrajornada_message.startswith("Não conforme")
    assert "máximo de 08:00" in item.intrajornada_message


def test_interjornada_requires_eleven_hours_between_days():
    previous = record(date(2026, 10, 28), time(20), time(23))
    current = record(date(2026, 10, 29), time(9), time(10), "2")
    check_rest_rules([previous, current], [], Coverage(True, date(2026, 10, 1), date(2026, 10, 31)))
    assert current.interjornada_message.startswith("Não conforme")
    assert "10:00" in current.interjornada_message


def test_unconfirmed_coverage_marks_rest_unverified():
    item = record(date(2026, 10, 28), time(8), time(9))
    check_rest_rules([item], [], Coverage())
    assert item.intrajornada_message.startswith("Não verificado")
    assert item.interjornada_message.startswith("Não verificado")


def test_invalid_request_for_same_teacher_blocks_rest_conclusion():
    item = record(date(2026, 10, 28), time(8), time(9))
    invalid = record(date(2026, 10, 28), time(9), time(10), "invalid")
    invalid.issues.append("Horário inválido")
    check_rest_rules([item, invalid], [], Coverage(True, date(2026, 10, 1), date(2026, 10, 31)))
    assert item.interjornada_message.startswith("Não verificado")
