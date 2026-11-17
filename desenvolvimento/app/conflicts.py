from __future__ import annotations

from collections import defaultdict
from datetime import date, time

from .models import ConflictDetail, Coverage, DwActivity, RequestRecord
from .normalize import unique_preserve


def _format_time(value: time) -> str:
    return value.strftime("%H:%M")


def _format_date(value: date) -> str:
    return value.strftime("%d/%m/%Y")


def check_conflicts(records: list[RequestRecord], activities: list[DwActivity] | None, coverage: Coverage | None, source_failed: str | None = None) -> list[ConflictDetail]:
    details: list[ConflictDetail] = []
    if source_failed:
        for record in records:
            record.result_message = f"Não verificado - {source_failed}."
        return details
    if activities is None:
        for record in records:
            record.result_message = "Não verificado - análise de conflitos não foi realizada."
        return details
    indexed: dict[tuple[str, date], list[DwActivity]] = defaultdict(list)
    requests_by_key: dict[tuple[str, date], list[RequestRecord]] = defaultdict(list)
    uncertain_teachers: set[str] = set()
    unknown_teacher = False
    for request in records:
        if request.issues:
            if request.matricula:
                uncertain_teachers.add(request.matricula)
            else:
                unknown_teacher = True
        elif request.matricula and request.activity_date:
            requests_by_key[(request.matricula, request.activity_date)].append(request)
    invalid_keys: set[tuple[str, date]] = set()
    for activity in activities:
        if activity.matricula and activity.activity_date:
            if activity.issues:
                invalid_keys.add((activity.matricula, activity.activity_date))
            else:
                indexed[(activity.matricula, activity.activity_date)].append(activity)
    for record in records:
        if record.issues:
            record.result_message = "Não verificado - " + "; ".join(record.issues) + "."
            continue
        key = (record.matricula, record.activity_date)
        hits = [activity for activity in indexed.get(key, []) if activity.start_time < record.end_time and activity.end_time > record.start_time]
        avulsos = [other for other in requests_by_key.get(key, []) if other is not record and other.start_time < record.end_time and other.end_time > record.start_time]
        if not hits and not avulsos:
            if key in invalid_keys or unknown_teacher or record.matricula in uncertain_teachers:
                record.result_message = "Não verificado - existem dados inválidos que podem afetar a comparação."
            elif not coverage or not coverage.contains(record.activity_date):
                record.result_message = "Não verificado - cobertura da base não confirmada para a data."
            else:
                record.result_message = "Sem conflito."
            continue
        types = unique_preserve([activity.activity_type.strip() if activity.activity_type else "Não informado" for activity in hits])
        record.result_type = "; ".join(types)
        lines: list[str] = []
        for activity in hits:
            activity_type = activity.activity_type.strip() if activity.activity_type else "Não informado"
            description = activity.description.strip() if activity.description else "Não informada"
            lines.append(f"Conflito com atividade do Agenda em {_format_date(activity.activity_date)}, das {_format_time(activity.start_time)} às {_format_time(activity.end_time)} - tipo: {activity_type}; atividade: {description}. Evento Avulso em {_format_date(record.activity_date)}, das {_format_time(record.start_time)} às {_format_time(record.end_time)}.")
            details.append(ConflictDetail(record.record_id, record.matricula, record.activity_date, record.start_time, record.end_time, activity.start_time, activity.end_time, activity_type, description))
        for other in avulsos:
            lines.append(f"Conflito com outra solicitação avulsa em {_format_date(other.activity_date)}, das {_format_time(other.start_time)} às {_format_time(other.end_time)} (registro {other.record_id}).")
            details.append(ConflictDetail(record.record_id, record.matricula, record.activity_date, record.start_time, record.end_time, other.start_time, other.end_time, "Evento avulso", f"Registro {other.record_id}"))
        message = "\n".join(lines)
        record.result_message = message if len(message) <= 32000 else f"Conflitos encontrados: {len(hits)}. Consulte a aba Detalhamento de conflitos."
    return details
