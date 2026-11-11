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
        if coverage is not None and coverage.confirmed and not coverage.contains(record.activity_date):
            record.result_message = "Não verificado - evento fora da cobertura confirmada do arquivo DW."
            continue
        key = (record.matricula, record.activity_date)
        if key in invalid_keys:
            record.result_message = "Não verificado - há atividade com dados inválidos no DW para a mesma matrícula e data."
            continue
        hits = [activity for activity in indexed.get(key, []) if activity.start_time < record.end_time and activity.end_time > record.start_time]
        if not hits:
            record.result_message = "Sem conflito."
            continue
        types = unique_preserve([activity.activity_type.strip() if activity.activity_type else "Não informado" for activity in hits])
        record.result_type = "; ".join(types)
        record.conflict_count = len(hits)
        lines: list[str] = []
        for activity in hits:
            activity_type = activity.activity_type.strip() if activity.activity_type else "Não informado"
            description = activity.description.strip() if activity.description else "Não informada"
            lines.append(f"Conflito com atividade do Agenda em {_format_date(activity.activity_date)}, das {_format_time(activity.start_time)} às {_format_time(activity.end_time)} - tipo: {activity_type}; atividade: {description}. Evento Avulso em {_format_date(record.activity_date)}, das {_format_time(record.start_time)} às {_format_time(record.end_time)}.")
            details.append(ConflictDetail(record.record_id, record.request_type, record.matricula, record.activity_date, record.start_time, record.end_time, activity.start_time, activity.end_time, activity_type, description))
        message = "\n".join(lines)
        record.result_message = message if len(message) <= 32000 else f"Conflitos encontrados: {len(hits)}. Consulte a aba Detalhamento de conflitos."
    return details
