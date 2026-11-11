from datetime import date
from zipfile import ZipFile

from openpyxl import load_workbook

from app.exporter import export_report
from app.models import RequestRecord, RunSummary


def test_export_contains_only_consolidation_data(tmp_path):
    record = RequestRecord({"Matrícula": "000123", "Data": date(2026, 10, 28)}, "letiva")
    summary = RunSummary("exec-1", "2026-10-28T08:00:00", letivas=1)
    output = export_report(tmp_path, summary, [record], [["letiva", "1. LETIVA", "origem.xlsx", "Processado", ""]], [])

    workbook = load_workbook(output, data_only=True)
    assert workbook.sheetnames == ["Resumo", "Letivas", "Não Letivas", "Pendências", "Arquivos processados"]
    headers = [cell.value for cell in workbook["Letivas"][1]]
    assert headers == ["Matrícula", "Data"]
    with ZipFile(output) as archive:
        worksheet_xml = archive.read("xl/worksheets/sheet2.xml").decode("utf-8")
        assert "<autoFilter" not in worksheet_xml
