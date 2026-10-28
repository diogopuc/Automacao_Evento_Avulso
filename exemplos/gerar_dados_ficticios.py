"""Gera arquivos fictícios isolados para demonstração; nunca altera as pastas de origem reais."""
from pathlib import Path
from datetime import date, time
from openpyxl import Workbook

ROOT = Path(__file__).resolve().parent / "dados_ficticios"

def save_request(path, registration, activity_date, start, end):
    wb = Workbook(); ws = wb.active; ws.title = "Solicitações"
    headers = ["Campo"] * 24; headers[1] = "Matrícula"; headers[5] = "Data de início da realização da atividade"; headers[22] = "Horário de início"; headers[23] = "Horário de término"
    ws.append(headers); row = [""] * 24; row[1], row[5], row[22], row[23] = registration, activity_date, start, end; ws.append(row); wb.save(path)

def main():
    (ROOT / "1. LETIVA").mkdir(parents=True, exist_ok=True); (ROOT / "2. NAO LETIVA").mkdir(exist_ok=True)
    save_request(ROOT / "1. LETIVA" / "letiva.xlsx", "000123", date(2026,10,28), time(8), time(9))
    save_request(ROOT / "2. NAO LETIVA" / "nao_letiva.xlsx", "000124", date(2026,10,28), time(10), time(11))
    wb = Workbook(); ws = wb.active; ws.title = "DW"; ws.append(["MATRICULA_ADP", "DATA", "HORARIO_INICIO HR Relogio", "HORARIO_FIM HR Relogio", "TIPO_ATIVIDADE", "DISCIPLINA_ATIVIDADE_NOME"]); ws.append(["000123", date(2026,10,28), time(8), time(8,45), "Letiva", "Disciplina fictícia"]); wb.save(ROOT / "dw_exportado.xlsx")
if __name__ == "__main__": main()
