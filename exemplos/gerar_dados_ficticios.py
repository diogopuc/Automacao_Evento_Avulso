"""Gera arquivos fictícios para testar a consolidação e a verificação local."""
from datetime import date, time
from pathlib import Path

from openpyxl import Workbook

ROOT = Path(__file__).resolve().parent / "dados_ficticios"


def save_request(path: Path, registration: str, activity_date: date, start: time, end: time) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Solicitações"
    headers = ["Campo"] * 24
    headers[1] = "Matrícula"
    headers[5] = "Data de início da realização da atividade"
    sheet.append(headers)
    headers[22], headers[23] = "Horário de início", "Horário de término"
    row = [""] * 24
    row[1], row[5], row[22], row[23] = registration, activity_date, start, end
    sheet.append(row)
    workbook.save(path)


def main() -> None:
    (ROOT / "1. LETIVA").mkdir(parents=True, exist_ok=True)
    (ROOT / "2. NAO LETIVA").mkdir(exist_ok=True)
    save_request(ROOT / "1. LETIVA" / "letiva.xlsx", "000123", date(2026, 10, 28), time(8), time(9))
    save_request(ROOT / "2. NAO LETIVA" / "nao_letiva.xlsx", "000124", date(2026, 10, 28), time(10), time(11))
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["MATRICULA_ADP", "DATA", "HORARIO_INICIO HR Relogio", "HORARIO_FIM HR Relogio", "TIPO_ATIVIDADE", "DISCIPLINA_ATIVIDADE_NOME"])
    sheet.append(["000123", date(2026, 10, 28), time(8), time(8, 45), "Letiva", "Disciplina fictícia"])
    workbook.save(ROOT / "base_dw.xlsx")


if __name__ == "__main__":
    main()
