import logging
from datetime import date, time

from openpyxl import Workbook, load_workbook

from app.models import CancellationToken, Coverage, Profile
from app.orchestrator import Processor


def test_complete_run_reports_conflicts_and_traceability(tmp_path):
    folder = tmp_path / "1. LETIVA"
    folder.mkdir()
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Matrícula", "Data", "Início", "Término"])
    sheet.append(["123", date(2026, 11, 17), time(8), time(10)])
    sheet.append(["123", date(2026, 11, 17), time(9), time(11)])
    workbook.save(folder / "eventos.xlsx")
    base = tmp_path / "base.xlsx"
    workbook = Workbook()
    workbook.active.append(["MATRICULA_ADP", "DATA", "HORARIO_INICIO HR Relogio", "HORARIO_FIM HR Relogio", "TIPO_ATIVIDADE", "DISCIPLINA_ATIVIDADE_NOME"])
    workbook.save(base)
    profile = Profile("p", "Teste", [], 1, 2, {
        "matricula": {"column": "A", "aliases": ["Matrícula"]},
        "data": {"column": "B", "aliases": ["Data"]},
        "inicio": {"column": "C", "aliases": ["Início"]},
        "fim": {"column": "D", "aliases": ["Término"]},
    })
    processor = Processor({"source_folders": [{"name": "1. LETIVA", "enabled": True}]}, logging.getLogger("test"))
    result = processor.run(tmp_path, tmp_path / "saida", profile, base, Coverage(True, date(2026, 11, 16), date(2026, 11, 18)), CancellationToken())
    assert processor.last_summary.conflicts == 2
    report = load_workbook(result, data_only=True)
    assert report["Rastreabilidade"].max_row == 3
    assert report["Detalhamento de conflitos"].max_row == 3
    assert report["Rastreabilidade"]["D2"].value == 2
    report.close()
