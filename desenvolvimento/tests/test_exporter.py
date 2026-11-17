from datetime import date, time
from zipfile import ZipFile

from openpyxl import load_workbook

from app.exporter import export_report
from app.models import RequestRecord, RunSummary


def test_export_includes_conflict_result_without_duplicate_filters(tmp_path):
    record = RequestRecord({"Matrícula": "000123", "Data": date(2026, 10, 28)}, "000123", date(2026, 10, 28), time(8), time(9), "id-1", result_message="Sem conflito.")
    summary = RunSummary("exec-1", "2026-10-28T08:00:00", "Arquivo exportado da view: base_dw.xlsx", letivas=1, no_conflicts=1)
    output = export_report(tmp_path, summary, [record], [], [["1. LETIVA", "origem.xlsx", "Processado", ""]], [])
    workbook = load_workbook(output, data_only=True)
    headers = [cell.value for cell in workbook["Letivas"][1]]
    assert "Resultado da verificação" in headers
    assert "Validação intrajornada" in headers and "Validação interjornada" in headers
    assert workbook["Letivas"].cell(2, headers.index("Resultado da verificação") + 1).value == "Sem conflito."
    with ZipFile(output) as archive:
        worksheet_xml = archive.read("xl/worksheets/sheet2.xml").decode("utf-8")
        assert "<autoFilter" not in worksheet_xml


def test_export_preserves_previous_report_before_replacing_it(tmp_path):
    first = RunSummary("first", "2026-11-17T08:00:00", "base")
    second = RunSummary("second", "2026-11-17T09:00:00", "base")
    target = export_report(tmp_path, first, [], [], [], [])
    assert target.name == "irregularidades_EV.xlsx"
    export_report(tmp_path, second, [], [], [], [])
    archives = list((tmp_path / "versionamento").glob("*.xlsx"))
    assert len(archives) == 1
    old_workbook = load_workbook(archives[0], read_only=True)
    assert old_workbook["Resumo"]["B1"].value == "first"
    old_workbook.close()
    current_workbook = load_workbook(target, read_only=True)
    assert current_workbook["Resumo"]["B1"].value == "second"
    current_workbook.close()


def test_report_highlights_only_individual_conflict_cells(tmp_path):
    record = RequestRecord(
        {"Matrícula": "123"}, "123", date(2026, 10, 28), time(8), time(9), "id",
        result_message="Conflito com atividade.",
        intrajornada_message="Conforme - intervalo adequado.",
        interjornada_message="Não conforme - descanso insuficiente.",
    )
    summary = RunSummary("exec", "2026-10-28T08:00:00", "base")
    output = export_report(tmp_path, summary, [record], [], [], [])
    workbook = load_workbook(output)
    sheet = workbook["Letivas"]
    headers = {cell.value: cell.column for cell in sheet[1]}
    assert all(cell.fill.fgColor.rgb[-6:] == "8A0538" for cell in sheet[1])
    assert sheet.cell(2, headers["Matrícula"]).fill.patternType is None
    assert sheet.cell(2, headers["Resultado da verificação"]).fill.fgColor.rgb[-6:] == "FF0000"
    assert sheet.cell(2, headers["Validação intrajornada"]).fill.patternType is None
    assert sheet.cell(2, headers["Validação interjornada"]).fill.fgColor.rgb[-6:] == "FF0000"
    assert not next(iter(sheet.tables.values())).tableStyleInfo.showRowStripes
    workbook.close()
