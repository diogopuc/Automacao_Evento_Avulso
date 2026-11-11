from datetime import date, time
from pathlib import Path

from openpyxl import Workbook

from app.models import CancellationToken, Profile
from app.reader import read_requests


def profile() -> Profile:
    return Profile("p", "Teste", ["Solicitações"], 1, 2, {
        "matricula": {"column": "B", "aliases": ["Matrícula"]},
        "data": {"column": "F", "aliases": ["Data"]},
        "inicio": {"column": "W", "aliases": ["Início"]},
        "fim": {"column": "X", "aliases": ["Término"]},
    })


def test_reader_reads_schedule_from_configured_columns(tmp_path: Path):
    file = tmp_path / "solicitacoes.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Solicitações"
    headers = [""] * 24
    headers[1], headers[5], headers[22], headers[23] = "Matrícula", "Data", "Início", "Término"
    sheet.append(headers)
    row = [""] * 24
    row[1], row[5], row[22], row[23] = "000123", date(2026, 10, 28), time(8), time(9)
    sheet.append(row)
    workbook.save(file)

    records, warnings = read_requests(file, "1. LETIVA", profile(), tmp_path, "exec", CancellationToken())

    assert not warnings
    assert records[0].matricula == "000123"
    assert records[0].start_time == time(8)
    assert not records[0].issues
