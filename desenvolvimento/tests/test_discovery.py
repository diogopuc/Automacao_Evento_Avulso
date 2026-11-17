from pathlib import Path
from app.discovery import discover_excel_files

def test_only_direct_excel_files_are_eligible(tmp_path):
    (tmp_path / "ok.xlsx").touch(); (tmp_path / "ok.xlsm").touch(); (tmp_path / "~$lock.xlsx").touch(); (tmp_path / "texto.csv").touch()
    historic = tmp_path / "2026"; historic.mkdir(); (historic / "nao_ler.xlsx").touch()
    files, ignored = discover_excel_files(tmp_path)
    assert [p.name for p in files] == ["ok.xlsm", "ok.xlsx"]
    assert {p.name for p in ignored} == {"~$lock.xlsx", "texto.csv"}
