from datetime import date, time

from app.conflicts import check_conflicts
from app.models import Coverage, DwActivity, RequestRecord


def request(start: time, end: time) -> RequestRecord:
    return RequestRecord({}, "0001", date(2026, 10, 28), start, end, "r")


def test_overlapping_activity_is_reported_as_conflict():
    record = request(time(8), time(9))
    activity = DwActivity("0001", date(2026, 10, 28), time(8), time(8, 45), "Letiva", "Aula")
    details = check_conflicts([record], [activity], Coverage())
    assert record.result_message.startswith("Conflito")
    assert len(details) == 1


def test_consecutive_intervals_are_not_conflicts():
    record = request(time(8, 45), time(9, 30))
    activity = DwActivity("0001", date(2026, 10, 28), time(8), time(8, 45), "Letiva", "Aula")
    check_conflicts([record], [activity], Coverage(True, date(2026, 10, 1), date(2026, 10, 31)))
    assert record.result_message == "Sem conflito."


def test_unconfirmed_coverage_never_claims_no_conflict():
    record = request(time(8), time(9))
    check_conflicts([record], [], Coverage())
    assert record.result_message.startswith("Não verificado")


def test_overlapping_requests_conflict_even_without_base_coverage():
    first = request(time(8), time(10))
    second = request(time(9), time(11))
    second.record_id = "outro"
    details = check_conflicts([first, second], [], Coverage())
    assert first.result_message.startswith("Conflito")
    assert second.result_message.startswith("Conflito")
    assert len(details) == 2
