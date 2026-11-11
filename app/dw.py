from __future__ import annotations

import re
import zipfile
from pathlib import Path
from typing import Callable, Iterator
from xml.etree import ElementTree as ET

from openpyxl.utils.cell import column_index_from_string, get_column_letter
from openpyxl.utils.datetime import from_excel

from .models import CancellationToken, DwActivity
from .normalize import normalize_id, normalized_header, parse_date, parse_time

REQUIRED_COLUMNS = {
    "matricula": "matricula_adp",
    "data": "data",
    "inicio": "horario_inicio hr relogio",
    "fim": "horario_fim hr relogio",
    "tipo": "tipo_atividade",
    "descricao": "disciplina_atividade_nome",
}
CELL_REFERENCE = re.compile(r"([A-Z]+)")
DIMENSION_REFERENCE = re.compile(rb"<dimension[^>]*ref=\"[^\"]*:(?:[A-Z]+)(\d+)\"")


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        stream = archive.open("xl/sharedStrings.xml")
    except KeyError:
        return []
    strings: list[str] = []
    with stream:
        for _, element in ET.iterparse(stream, events=("end",)):
            if element.tag.endswith("}si"):
                strings.append("".join(node.text or "" for node in element.iter() if node.tag.endswith("}t")))
                element.clear()
    return strings


def _cell_value(cell: ET.Element, shared_strings: list[str]):
    cell_type = cell.attrib.get("t")
    raw = next((child.text for child in cell if child.tag.endswith("}v")), None)
    if cell_type == "inlineStr":
        return "".join(node.text or "" for node in cell.iter() if node.tag.endswith("}t"))
    if raw is None:
        return None
    if cell_type == "s":
        try:
            return shared_strings[int(raw)]
        except (IndexError, ValueError):
            return None
    if cell_type == "b":
        return raw == "1"
    if cell_type in {"str", "e"}:
        return raw
    try:
        value = float(raw)
        return int(value) if value.is_integer() else value
    except ValueError:
        return raw


def _rows(path: Path) -> tuple[int, Iterator[tuple[int, dict[str, object]]]]:
    archive = zipfile.ZipFile(path)
    shared_strings = _shared_strings(archive)
    try:
        with archive.open("xl/worksheets/sheet1.xml") as stream:
            prefix = stream.read(65536)
    except KeyError as exc:
        archive.close()
        raise ValueError("Arquivo da view não possui uma planilha de dados válida.") from exc
    dimension = DIMENSION_REFERENCE.search(prefix)
    total = max(int(dimension.group(1)) - 1, 0) if dimension else 0

    def iterator() -> Iterator[tuple[int, dict[str, object]]]:
        try:
            with archive.open("xl/worksheets/sheet1.xml") as stream:
                for _, element in ET.iterparse(stream, events=("end",)):
                    if not element.tag.endswith("}row"):
                        continue
                    row_number = int(element.attrib.get("r", "0"))
                    values: dict[str, object] = {}
                    for cell in element:
                        if not cell.tag.endswith("}c"):
                            continue
                        reference = cell.attrib.get("r", "")
                        match = CELL_REFERENCE.match(reference)
                        if match:
                            values[match.group(1)] = _cell_value(cell, shared_strings)
                    yield row_number, values
                    element.clear()
        finally:
            archive.close()

    return total, iterator()


def _headers(first_row: dict[str, object]) -> dict[str, str]:
    by_name = {normalized_header(value): column for column, value in first_row.items() if value not in (None, "")}
    missing = [label for label in REQUIRED_COLUMNS.values() if label not in by_name]
    if missing:
        raise ValueError(f"Arquivo da view sem coluna obrigatória: {missing[0]}")
    return {field: by_name[label] for field, label in REQUIRED_COLUMNS.items()}


def _date_value(value: object):
    if isinstance(value, (int, float)):
        try:
            return from_excel(value)
        except (TypeError, ValueError):
            return value
    return value


def inspect_dw_export(path: Path) -> tuple[str, int]:
    if not path.is_file():
        raise ValueError("Arquivo da view não encontrado.")
    total, rows = _rows(path)
    try:
        _, header = next(rows)
        _headers(header)
    except StopIteration as exc:
        raise ValueError("Arquivo da view está vazio.") from exc
    finally:
        rows.close()
    return "Planilha 1", total


def load_dw_export(
    path: Path,
    token: CancellationToken | None = None,
    on_progress: Callable[[int, int], None] | None = None,
    wanted_keys: set[tuple[str | None, object]] | None = None,
) -> list[DwActivity]:
    if not path.is_file():
        raise ValueError("Arquivo da view não encontrado.")
    total, rows = _rows(path)
    try:
        _, header = next(rows)
    except StopIteration as exc:
        raise ValueError("Arquivo da view está vazio.") from exc
    columns = _headers(header)
    activities: list[DwActivity] = []
    processed = 0
    for row_number, row in rows:
        processed += 1
        if token and processed % 500 == 0:
            token.raise_if_cancelled()
        matricula = normalize_id(row.get(columns["matricula"]))
        activity_date = parse_date(_date_value(row.get(columns["data"])))
        start_time = parse_time(_date_value(row.get(columns["inicio"])))
        end_time = parse_time(_date_value(row.get(columns["fim"])))
        key = (matricula, activity_date)
        if wanted_keys is not None and key not in wanted_keys:
            if on_progress and processed % 1000 == 0:
                on_progress(processed, total)
            continue
        issues: list[str] = []
        if not matricula:
            issues.append("Matrícula inválida no arquivo da view")
        if not activity_date:
            issues.append("Data inválida no arquivo da view")
        if not start_time or not end_time or end_time <= start_time:
            issues.append("Intervalo inválido no arquivo da view")
        activities.append(DwActivity(matricula, activity_date, start_time, end_time, str(row.get(columns["tipo"]) or ""), str(row.get(columns["descricao"]) or ""), row_number, tuple(issues)))
        if on_progress and processed % 1000 == 0:
            on_progress(processed, total)
    if token:
        token.raise_if_cancelled()
    if on_progress:
        on_progress(processed, total)
    return activities
