from datetime import date, time
from app.conflicts import check_conflicts
from app.models import Coverage, DwActivity, RequestRecord

def request(start, end, matricula="0001", day=date(2026,10,28)):
    return RequestRecord({}, "letiva", matricula, day, start, end, "a.xlsx", "a.xlsx", "A", 2, "1. LETIVA", "p", "r", "e")

def activity(start, end, matricula="0001", day=date(2026,10,28)):
    return DwActivity(matricula, day, start, end, "Letiva", "Aula")

def test_overlap_and_consecutive_intervals():
    records = [request(time(8), time(9)), request(time(8,45), time(9,30)), request(time(7), time(8))]
    details = check_conflicts(records, [activity(time(8), time(8,45))], Coverage(True, date(2026,10,1), date(2026,10,31)))
    assert len(details) == 1
    assert records[0].result_message.startswith("Conflito")
    assert records[1].result_message == "Sem conflito."
    assert records[2].result_message == "Sem conflito."

def test_multiple_conflicts_are_all_retained():
    record = request(time(8), time(10))
    details = check_conflicts([record], [activity(time(8), time(8,45)), activity(time(9), time(9,45))], Coverage(True, date(2026,10,1), date(2026,10,31)))
    assert len(details) == 2 and record.conflict_count == 2 and record.result_type == "Letiva"

def test_invalid_request_is_never_a_no_conflict():
    record = request(time(8), time(8))
    record.issues.append("Término igual ou anterior ao início")
    check_conflicts([record], [], Coverage(True, date(2026,10,1), date(2026,10,31)))
    assert record.result_message.startswith("Não verificado")

def test_different_teacher_or_date_never_matches():
    records = [request(time(8), time(9), "0001"), request(time(8), time(9), "0002")]
    other_day = date(2026, 10, 29)
    check_conflicts(records, [activity(time(8), time(8,45), "0002", other_day)], Coverage(True, date(2026,10,1), date(2026,10,31)))
    assert [r.result_message for r in records] == ["Sem conflito.", "Sem conflito."]

def test_contained_and_identical_intervals_conflict():
    records = [request(time(8,15), time(8,30)), request(time(8), time(8,45))]
    check_conflicts(records, [activity(time(8), time(8,45))], Coverage(True, date(2026,10,1), date(2026,10,31)))
    assert all(r.result_message.startswith("Conflito") for r in records)

def test_unconfirmed_file_coverage_is_not_verified():
    record = request(time(8), time(9))
    check_conflicts([record], [activity(time(8), time(8,45))], Coverage())
    assert record.result_message.startswith("Não verificado")

def test_source_failure_is_not_no_conflict():
    record = request(time(8), time(9))
    check_conflicts([record], [], Coverage(), "falha de teste")
    assert record.result_message == "Não verificado - falha de teste."
