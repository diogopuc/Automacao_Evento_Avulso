from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import bindparam, create_engine, text

from .models import Coverage, DwActivity
from .normalize import normalized_header, normalize_id, parse_date, parse_time

DW_ALIASES = {
    "matricula": ["matricula_adp"], "data": ["data"], "inicio": ["horario_inicio hr relogio"],
    "fim": ["horario_fim hr relogio"], "tipo": ["tipo_atividade"], "descricao": ["disciplina_atividade_nome"],
}


def _find_columns(columns: list[Any]) -> dict[str, str]:
    index = {normalized_header(value): str(value) for value in columns}
    resolved = {}
    for field, aliases in DW_ALIASES.items():
        found = [index[alias] for alias in aliases if alias in index]
        if len(found) != 1: raise ValueError(f"Arquivo DW sem coluna obrigatória: {field}")
        resolved[field] = found[0]
    return resolved


def normalize_dw_frame(frame: pd.DataFrame) -> list[DwActivity]:
    columns = _find_columns(list(frame.columns)); records = []
    for idx, row in frame.iterrows():
        activity = DwActivity(matricula=normalize_id(row[columns["matricula"]]), activity_date=parse_date(row[columns["data"]]), start_time=parse_time(row[columns["inicio"]]), end_time=parse_time(row[columns["fim"]]), activity_type=None if pd.isna(row[columns["tipo"]]) else str(row[columns["tipo"]]), description=None if pd.isna(row[columns["descricao"]]) else str(row[columns["descricao"]]), source_row=int(idx) + 2)
        issues = []
        if not activity.matricula: issues.append("Matrícula inválida no DW")
        if not activity.activity_date: issues.append("Data inválida no DW")
        if not activity.start_time or not activity.end_time or activity.end_time <= activity.start_time: issues.append("Intervalo inválido no DW")
        records.append(DwActivity(**{**activity.__dict__, "issues": tuple(issues)}))
    return records


def load_dw_export(path: Path) -> list[DwActivity]:
    return normalize_dw_frame(pd.read_excel(path, dtype=object))


def build_sqlalchemy_url(sql_config: dict[str, Any], password: str | None = None) -> str:
    from sqlalchemy.engine import URL
    query = {"driver": sql_config["odbc_driver"], "Encrypt": "yes" if sql_config.get("encrypt", True) else "no", "TrustServerCertificate": "yes" if sql_config.get("trust_server_certificate", False) else "no"}
    if sql_config.get("authentication") == "windows":
        query["Trusted_Connection"] = "yes"; username = None
    else:
        username = sql_config.get("username")
    return str(URL.create("mssql+pyodbc", username=username, password=password, host=sql_config.get("server"), database=sql_config.get("database"), query=query))


def test_sql_connection(sql_config: dict[str, Any], password: str | None = None) -> None:
    engine = create_engine(build_sqlalchemy_url(sql_config, password), connect_args={"timeout": sql_config.get("connect_timeout_seconds", 15)})
    with engine.connect() as connection: connection.execute(text("SELECT 1"))


def query_dw(sql_config: dict[str, Any], matriculas: set[str], first_date: date, last_date: date, password: str | None = None) -> list[DwActivity]:
    """Batched and parameterized. No status filter is applied."""
    engine = create_engine(build_sqlalchemy_url(sql_config, password), connect_args={"timeout": sql_config.get("connect_timeout_seconds", 15)})
    statement = text("""
SELECT [MATRICULA_ADP], [DATA], [HORARIO_INICIO HR Relogio], [HORARIO_FIM HR Relogio],
       [TIPO_ATIVIDADE], [DISCIPLINA_ATIVIDADE_NOME], [STATUS], [TIPO_CARTAO], [DATA_EXTRACAO]
FROM [ANALYTICS_AT].[Relatório de Atividades do Docente]
WHERE [DATA] >= :first_date AND [DATA] <= :last_date AND [MATRICULA_ADP] IN :matriculas
""").bindparams(bindparam("matriculas", expanding=True))
    frames = []
    with engine.connect() as connection:
        connection.connection.timeout = sql_config.get("query_timeout_seconds", 90)
        for start in range(0, len(matriculas), 1800):
            batch = list(matriculas)[start:start + 1800]
            frames.append(pd.read_sql(statement, connection, params={"first_date": first_date, "last_date": last_date, "matriculas": batch}))
    return normalize_dw_frame(pd.concat(frames, ignore_index=True) if frames else pd.DataFrame())
