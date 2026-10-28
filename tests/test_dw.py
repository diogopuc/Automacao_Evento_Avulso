from datetime import date, time

from openpyxl import Workbook

from app.dw import inspect_dw_export, load_dw_export
from app.models import CancellationToken


def test_dw_export_is_streamed_and_validated(tmp_path):
    file = tmp_path / "base_dw.xlsx"
    workbook = Workbook(); sheet = workbook.active; sheet.title = "View"
    sheet.append(["MATRICULA_ADP", "DATA", "HORARIO_INICIO HR Relogio", "HORARIO_FIM HR Relogio", "TIPO_ATIVIDADE", "DISCIPLINA_ATIVIDADE_NOME"])
    sheet.append(["000123", date(2026,10,28), time(8), time(8,45), "Letiva", "Disciplina"])
    workbook.save(file)
    assert inspect_dw_export(file) == ("Planilha 1", 1)
    progress = []
    records = load_dw_export(file, CancellationToken(), lambda done, total: progress.append((done, total)))
    assert records[0].matricula == "000123" and not records[0].issues
    assert progress == [(1, 1)]


def test_dw_export_can_keep_only_requested_keys(tmp_path):
    file = tmp_path / "base_dw.xlsx"; workbook = Workbook(); sheet = workbook.active
    sheet.append(["MATRICULA_ADP", "DATA", "HORARIO_INICIO HR Relogio", "HORARIO_FIM HR Relogio", "TIPO_ATIVIDADE", "DISCIPLINA_ATIVIDADE_NOME"])
    sheet.append(["000123", date(2026,10,28), time(8), time(8,45), "Letiva", "Manter"])
    sheet.append(["000999", date(2026,10,28), time(8), time(8,45), "Letiva", "Ignorar"]); workbook.save(file)
    records = load_dw_export(file, wanted_keys={("000123", date(2026,10,28))})
    assert len(records) == 1 and records[0].description == "Manter"
