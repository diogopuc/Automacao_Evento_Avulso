"""Gera arquivos fictícios para testar somente a consolidação."""
from datetime import date
from pathlib import Path

from openpyxl import Workbook

ROOT = Path(__file__).resolve().parent / "dados_ficticios"


def save_request(path: Path, registration: str, activity_date: date) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Solicitações"
    headers = ["Campo"] * 6
    headers[1] = "Matrícula"
    headers[5] = "Data de início da realização da atividade"
    sheet.append(headers)
    row = [""] * 6
    row[1], row[5] = registration, activity_date
    sheet.append(row)
    workbook.save(path)


def main() -> None:
    (ROOT / "1. LETIVA").mkdir(parents=True, exist_ok=True)
    (ROOT / "2. NAO LETIVA").mkdir(exist_ok=True)
    save_request(ROOT / "1. LETIVA" / "letiva.xlsx", "000123", date(2026, 10, 28))
    save_request(ROOT / "2. NAO LETIVA" / "nao_letiva.xlsx", "000124", date(2026, 10, 28))


if __name__ == "__main__":
    main()
