from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from openpyxl import load_workbook

from .models import DwActivity
from .normalize import normalized_header, normalize_id, parse_date, parse_time

DW_ALIASES = {
    "matricula": ["matricula_adp"], "data": ["data"], "inicio": ["horario_inicio hr relogio"],
    "fim": ["horario_fim hr relogio"], "tipo": ["tipo_atividade"], "descricao": ["disciplina_atividade_nome"],
}


def _find_columns(headers: list[Any]) -> dict[str, int]:
    normalized = {normalized_header(value): index for index, value in enumerate(headers)}
    resolved: dict[str, int] = {}
    for field, aliases in DW_ALIASES.items():
        matches = [normalized[alias] for alias in aliases if alias in normalized]
        if len(matches) != 1:
            raise ValueError(f"Arquivo da view sem coluna obrigatória: {field}")
        resolved[field] = matches[0]
    return resolved


def _value(row: tuple[Any, ...], index: int) -> Any:
    return row[index] if index < len(row) else None


def _activity_from_row(row: tuple[Any, ...], columns: dict[str, int], source_row: int) -> DwActivity:
    raw_type, raw_description = _value(row, columns["tipo"]), _value(row, columns["descricao"])
    activity = DwActivity(
        matricula=normalize_id(_value(row, columns["matricula"])),
        activity_date=parse_date(_value(row, columns["data"])),
        start_time=parse_time(_value(row, columns["inicio"])),
        end_time=parse_time(_value(row, columns["fim"])),
        activity_type=None if raw_type is None else str(raw_type),
        description=None if raw_description is None else str(raw_description),
        source_row=source_row,
    )
    issues = []
    if not activity.matricula:
        issues.append("Matrícula inválida no arquivo da view")
    if not activity.activity_date:
        issues.append("Data inválida no arquivo da view")
    if not activity.start_time or not activity.end_time or activity.end_time <= activity.start_time:
        issues.append("Intervalo inválido no arquivo da view")
    return DwActivity(**{**activity.__dict__, "issues": tuple(issues)})


def inspect_dw_export(path: Path) -> tuple[str, int]:
    """Checks headers without reading the entire Excel extract."""
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        sheet = workbook.active
        headers = list(next(sheet.iter_rows(min_row=1, max_row=1, values_only=True), ()))
        _find_columns(headers)
        return sheet.title, max(sheet.max_row - 1, 0)
    finally:
        workbook.close()


def load_dw_export(path: Path, token=None, on_progress: Callable[[int, int], None] | None = None, wanted_keys: set[tuple[str, object]] | None = None) -> list[DwActivity]:
    """Streams a large export and periodically reports progress/cancellation."""
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        sheet = workbook.active
        headers = list(next(sheet.iter_rows(min_row=1, max_row=1, values_only=True), ()))
        columns = _find_columns(headers)
        total = max(sheet.max_row - 1, 0)
        records: list[DwActivity] = []
        for source_row, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
            if token and source_row % 500 == 0:
                token.raise_if_cancelled()
            activity = _activity_from_row(row, columns, source_row)
            if wanted_keys is None or (activity.matricula, activity.activity_date) in wanted_keys:
                records.append(activity)
            if on_progress and (source_row % 1_000 == 0 or source_row == sheet.max_row):
                on_progress(source_row - 1, total)
        if token:
            token.raise_if_cancelled()
        return records
    finally:
        workbook.close()
