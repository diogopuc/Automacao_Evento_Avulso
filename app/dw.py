from __future__ import annotations

import re
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterator
from xml.etree import ElementTree as ET

from openpyxl.utils.datetime import from_excel

from .models import DwActivity
from .normalize import normalized_header, normalize_id, parse_date, parse_time

DW_ALIASES = {
    "matricula": ["matricula_adp"], "data": ["data"], "inicio": ["horario_inicio hr relogio"],
    "fim": ["horario_fim hr relogio"], "tipo": ["tipo_atividade"], "descricao": ["disciplina_atividade_nome"],
}
CELL_REF = re.compile(r"([A-Z]+)")


def _local_name(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _column_index(reference: str) -> int:
    letters = CELL_REF.match(reference).group(1)
    value = 0
    for char in letters:
        value = value * 26 + ord(char) - 64
    return value - 1


def _cell_text(cell: ET.Element, shared_strings: list[str]) -> Any:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(node.text or "" for node in cell.iter() if _local_name(node) == "t")
    raw = next((node.text for node in cell if _local_name(node) == "v"), None)
    if raw is None:
        return None
    if cell_type == "s":
        return shared_strings[int(raw)]
    if cell_type == "b":
        return raw == "1"
    try:
        return float(raw) if "." in raw else int(raw)
    except ValueError:
        return raw


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        with archive.open("xl/sharedStrings.xml") as source:
            root = ET.parse(source).getroot()
    except KeyError:
        return []
    return ["".join(node.text or "" for node in item.iter() if _local_name(node) == "t") for item in root if _local_name(item) == "si"]


def _rows(path: Path) -> tuple[int, Iterator[dict[int, Any]]]:
    """Streams sheet1 XML directly, avoiding a full openpyxl workbook load."""
    archive = zipfile.ZipFile(path)
    shared_strings = _shared_strings(archive)
    source = archive.open("xl/worksheets/sheet1.xml")
    prefix = source.read(8192).decode("utf-8", errors="ignore")
    source.close()
    reference = re.search(r'<dimension[^>]*ref="([^"]+)"', prefix)
    match = re.search(r":?[A-Z]+(\d+)$", reference.group(1)) if reference else None
    total = max(int(match.group(1)) - 1, 0) if match else 0
    source = archive.open("xl/worksheets/sheet1.xml")

    def iterator() -> Iterator[dict[int, Any]]:
        try:
            for _, element in ET.iterparse(source, events=("end",)):
                if _local_name(element) == "row":
                    row = {_column_index(cell.attrib["r"]): _cell_text(cell, shared_strings) for cell in element if _local_name(cell) == "c"}
                    yield row
                    element.clear()
        finally:
            source.close()
            archive.close()

    return total, iterator()


def _find_columns(headers: dict[int, Any]) -> dict[str, int]:
    normalized = {normalized_header(value): index for index, value in headers.items()}
    resolved: dict[str, int] = {}
    for field, aliases in DW_ALIASES.items():
        matches = [normalized[alias] for alias in aliases if alias in normalized]
        if len(matches) != 1:
            raise ValueError(f"Arquivo da view sem coluna obrigatória: {field}")
        resolved[field] = matches[0]
    return resolved


def _as_date(value: Any):
    if isinstance(value, (int, float)):
        converted = from_excel(value)
        return converted.date() if isinstance(converted, datetime) else converted
    return parse_date(value)


def _as_time(value: Any):
    if isinstance(value, (int, float)):
        converted = from_excel(value)
        return converted.time() if isinstance(converted, datetime) else converted
    return parse_time(value)


def _activity_from_row(row: dict[int, Any], columns: dict[str, int], source_row: int) -> DwActivity:
    raw_type, raw_description = row.get(columns["tipo"]), row.get(columns["descricao"])
    activity = DwActivity(
        matricula=normalize_id(row.get(columns["matricula"])),
        activity_date=_as_date(row.get(columns["data"])),
        start_time=_as_time(row.get(columns["inicio"])),
        end_time=_as_time(row.get(columns["fim"])),
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
    total, rows = _rows(path)
    try:
        headers = next(rows, {})
        _find_columns(headers)
        return "Planilha 1", total
    finally:
        rows.close()


def load_dw_export(path: Path, token=None, on_progress: Callable[[int, int], None] | None = None, wanted_keys: set[tuple[str, object]] | None = None) -> list[DwActivity]:
    """Streams a large Excel export directly from the XLSX XML."""
    total, rows = _rows(path)
    try:
        headers = next(rows, {})
        columns = _find_columns(headers)
        records: list[DwActivity] = []
        for source_row, row in enumerate(rows, start=2):
            if token and source_row % 500 == 0:
                token.raise_if_cancelled()
            activity = _activity_from_row(row, columns, source_row)
            if wanted_keys is None or (activity.matricula, activity.activity_date) in wanted_keys:
                records.append(activity)
            if on_progress and (source_row % 1_000 == 0 or source_row - 1 == total):
                on_progress(source_row - 1, total)
        if token:
            token.raise_if_cancelled()
        return records
    finally:
        rows.close()
