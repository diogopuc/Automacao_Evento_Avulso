from pathlib import Path

from openpyxl import Workbook

from app.models import CancellationToken, Profile
from app.reader import read_requests


def profile() -> Profile:
    return Profile("p", "Teste", ["Solicitações"], 1, 2, {
        "matricula": {"column": "B", "aliases": ["Matrícula"]},
        "data": {"column": "F", "aliases": ["Data"]},
    })


def test_reader_preserves_source_values(tmp_path: Path):
    file = tmp_path / "solicitacoes.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Solicitações"
    headers = ["" for _ in range(6)]
    headers[1], headers[5] = "Matrícula", "Data"
    sheet.append(headers)
    row = ["" for _ in range(6)]
    row[1], row[5] = "000123", "28/10/2026"
    sheet.append(row)
    workbook.save(file)

    records, warnings = read_requests(file, "letiva", profile(), CancellationToken())

    assert not warnings
    assert records[0].request_type == "letiva"
    assert records[0].values["Matrícula"] == "000123"


def test_reader_rejects_ambiguous_template(tmp_path: Path):
    file = tmp_path / "solicitacoes.xlsx"
    workbook = Workbook()
    workbook.active.title = "Solicitações"
    workbook.active.append(["Matrícula", "Data"])
    workbook.create_sheet("Outra").append(["Matrícula", "Data"])
    workbook.save(file)
    ambiguous_profile = profile()
    ambiguous_profile.sheet_names = []

    try:
        read_requests(file, "letiva", ambiguous_profile, CancellationToken())
    except ValueError as exc:
        assert "não reconheceu" in str(exc) or "ambíguo" in str(exc)
    else:
        raise AssertionError("O arquivo ambíguo deveria ser rejeitado")
