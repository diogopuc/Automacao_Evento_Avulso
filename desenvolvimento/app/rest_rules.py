from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta

from .models import Coverage, DwActivity, RequestRecord

MINIMUM_INTERJORNADA = timedelta(hours=11)
MAXIMUM_JORNADA = timedelta(hours=8)
MINIMUM_INTRA_5_TO_6 = timedelta(minutes=15)
MINIMUM_INTRA_7_TO_8 = timedelta(hours=1)


def _duration_text(value: timedelta) -> str:
    minutes = max(0, int(value.total_seconds() // 60))
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _merge(intervals: list[tuple[time, time]], activity_date: date) -> list[tuple[datetime, datetime]]:
    scheduled = sorted((datetime.combine(activity_date, start), datetime.combine(activity_date, end)) for start, end in intervals)
    merged: list[tuple[datetime, datetime]] = []
    for start, end in scheduled:
        if not merged or start > merged[-1][1]:
            merged.append((start, end))
        else:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
    return merged


def _intra_message(intervals: list[tuple[datetime, datetime]]) -> str:
    worked = sum((end - start for start, end in intervals), timedelta())
    if worked < timedelta(hours=5):
        return f"Conforme - jornada diária de {_duration_text(worked)}; intervalo intrajornada não aplicável."
    if worked > MAXIMUM_JORNADA:
        return f"Não conforme - jornada diária de {_duration_text(worked)} excede o máximo de 08:00."
    required = MINIMUM_INTRA_7_TO_8 if worked >= timedelta(hours=7) else MINIMUM_INTRA_5_TO_6
    breaks = [next_start - previous_end for (_, previous_end), (next_start, _) in zip(intervals, intervals[1:])]
    largest = max(breaks, default=timedelta())
    if largest >= required:
        return f"Conforme - jornada diária de {_duration_text(worked)} com pausa de {_duration_text(largest)} (mínimo: {_duration_text(required)})."
    return f"Não conforme - jornada diária de {_duration_text(worked)} requer pausa mínima de {_duration_text(required)}; maior pausa encontrada: {_duration_text(largest)}."


def _inter_message(key: tuple[str, date], schedules: dict[tuple[str, date], list[tuple[datetime, datetime]]]) -> str:
    matricula, activity_date = key
    current = schedules[key]
    violations: list[str] = []
    checks = [
        (activity_date - timedelta(days=1), schedules.get((matricula, activity_date - timedelta(days=1))), current[0][0], "anterior"),
        (activity_date + timedelta(days=1), schedules.get((matricula, activity_date + timedelta(days=1))), current[-1][1], "seguinte"),
    ]
    comparable = False
    for adjacent_date, adjacent, current_limit, direction in checks:
        if not adjacent:
            continue
        comparable = True
        gap = current_limit - adjacent[-1][1] if direction == "anterior" else adjacent[0][0] - current_limit
        if gap < MINIMUM_INTERJORNADA:
            violations.append(f"{adjacent_date:%d/%m/%Y}: {_duration_text(gap)}")
    if violations:
        return "Não conforme - descanso interjornada inferior a 11:00 em " + "; ".join(violations) + "."
    if comparable:
        return "Conforme - descanso interjornada mínimo de 11:00 atendido."
    return "Conforme - não há atividade no dia adjacente para restringir a interjornada."


def check_rest_rules(records: list[RequestRecord], activities: list[DwActivity] | None, coverage: Coverage | None = None, source_failed: str | None = None) -> None:
    if source_failed or activities is None:
        message = "Não verificado - base da view indisponível para calcular descansos."
        for record in records:
            record.intrajornada_message = message
            record.interjornada_message = message
        return

    schedules_raw: dict[tuple[str, date], list[tuple[time, time]]] = defaultdict(list)
    invalid_keys: set[tuple[str, date]] = set()
    for activity in activities:
        if not activity.matricula or not activity.activity_date:
            continue
        key = (activity.matricula, activity.activity_date)
        if activity.issues:
            invalid_keys.add(key)
        else:
            schedules_raw[key].append((activity.start_time, activity.end_time))
    for record in records:
        if not record.issues:
            schedules_raw[(record.matricula, record.activity_date)].append((record.start_time, record.end_time))

    schedules = {key: _merge(intervals, key[1]) for key, intervals in schedules_raw.items()}
    for record in records:
        if record.issues:
            message = "Não verificado - " + "; ".join(record.issues) + "."
            record.intrajornada_message = message
            record.interjornada_message = message
            continue
        key = (record.matricula, record.activity_date)
        adjacent_keys = {key, (record.matricula, record.activity_date - timedelta(days=1)), (record.matricula, record.activity_date + timedelta(days=1))}
        if invalid_keys.intersection(adjacent_keys):
            message = "Não verificado - há atividade da base com dados inválidos no período analisado."
            record.intrajornada_message = message
            record.interjornada_message = message
            continue
        if coverage and coverage.confirmed and not all(coverage.contains(day) for _, day in adjacent_keys):
            message = "Não verificado - período necessário fora da cobertura confirmada da base."
            record.intrajornada_message = message
            record.interjornada_message = message
            continue
        record.intrajornada_message = _intra_message(schedules[key])
        record.interjornada_message = _inter_message(key, schedules)
