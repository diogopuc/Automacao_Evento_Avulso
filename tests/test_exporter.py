from datetime import date, time
from zipfile import ZipFile

from openpyxl import load_workbook

from app.exporter import export_report
from app.models import RequestRecord, RunSummary


def test_export_includes_conflict_result_without_duplicate_filters(tmp_path):
    record = RequestRecord({"Matrícula": "000123", "Data": date(2026, 10, 28)}, "000123", date(2026, 10, 28), time(8), time(9), "origem.xlsx", "1. LETIVA/origem.xlsx", "Solicitações", 2, "1. LETIVA", "novo", "id-1", "exec-1", result_message="Sem conflito.")
    summary = RunSummary("exec-1", "2026-10-28T08:00:00", "Arquivo exportado da view: base_dw.xlsx", letivas=1, no_conflicts=1)
    output = export_report(tmp_path, summary, [record], [], [["1. LETIVA", "origem.xlsx", "Processado", ""]], [])
    workbook = load_workbook(output, data_only=True)
    headers = [cell.value for cell in workbook["Letivas"][1]]
    assert "Resultado da verificação" in headers
    assert workbook["Letivas"].cell(2, headers.index("Resultado da verificação") + 1).value == "Sem conflito."
    with ZipFile(output) as archive:
        worksheet_xml = archive.read("xl/worksheets/sheet2.xml").decode("utf-8")
        assert "<autoFilter" not in worksheet_xml
