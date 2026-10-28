from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from .conflicts import check_conflicts
from .discovery import discover_excel_files, output_is_safe, validate_input_directory
from .dw import load_dw_export, query_dw
from .exporter import export_report
from .models import CancelledError, CancellationToken, Coverage, RunSummary
from .profiles import Profile
from .reader import read_requests


class Processor:
    def __init__(self, config: dict, logger: logging.Logger, progress=lambda *_: None):
        self.config, self.logger, self.progress = config, logger, progress
        self.last_summary = None

    def validate(self, input_dir: Path):
        from .config import source_folders
        return validate_input_directory(input_dir, source_folders(self.config))

    def run(self, input_dir: Path, output_dir: Path, profile: Profile, source_kind: str, dw_file: Path | None, coverage: Coverage | None, token: CancellationToken, password: str | None = None) -> Path:
        from .config import source_folders
        execution_id = str(uuid4()); started = datetime.now().isoformat(timespec="seconds")
        source_label = "SQL Server" if source_kind == "sql" else f"Arquivo DW: {dw_file.name if dw_file else 'não selecionado'}"
        summary = RunSummary(execution_id, started, source_label)
        folders = source_folders(self.config)
        if not output_is_safe(output_dir, input_dir, folders): raise ValueError("A pasta de saída não pode ficar dentro de uma pasta de origem habilitada.")
        self.progress("Validando configurações", None, None); found, missing = self.validate(input_dir)
        if not found: raise ValueError("Nenhuma pasta de origem habilitada foi encontrada.")
        issues = [["Pasta ausente", folder.name, "Pasta habilitada não encontrada"] for folder in missing]
        file_rows, records = [], []
        self.progress("Localizando arquivos", None, None)
        work = []
        for folder, path in found:
            eligible, ignored = discover_excel_files(path); summary.files_found += len(eligible)
            for item in ignored: file_rows.append([folder.request_type, folder.name, item.name, "Ignorado", "Temporário ou formato não suportado"])
            if not eligible: issues.append(["Pasta sem arquivo", folder.name, "Nenhum arquivo disponível para processamento"])
            work.extend((folder, item) for item in eligible)
        if not work: raise ValueError("Nenhum arquivo Excel elegível foi encontrado nas pastas disponíveis.")
        for index, (folder, file) in enumerate(work, 1):
            token.raise_if_cancelled(); self.progress("Lendo solicitações", 5 + int(index / len(work) * 45), file.name)
            try:
                loaded, warnings = read_requests(file, folder.name, folder.request_type, profile, input_dir, execution_id, token)
                records.extend(loaded); summary.files_processed += 1; file_rows.append([folder.request_type, folder.name, file.name, "Processado", "; ".join(warnings)])
                issues.extend([["Leitura", file.name, warning] for warning in warnings])
            except CancelledError:
                self.logger.info("Cancelamento solicitado durante a leitura de %s", file.name)
                raise
            except Exception as exc:
                summary.files_with_error += 1; summary.status = "Concluído com pendências"; file_rows.append([folder.request_type, folder.name, file.name, "Erro", str(exc)]); issues.append(["Arquivo", file.name, str(exc)]); self.logger.exception("Falha ao ler arquivo %s", file.name)
        summary.letivas = sum(r.request_type == "letiva" for r in records); summary.nao_letivas = sum(r.request_type == "nao_letiva" for r in records)
        if source_kind == "none": activities, failed = None, None
        else:
            self.progress("Consultando ou carregando DW", 55, None)
            try:
                if source_kind == "file":
                    if not dw_file: raise ValueError("Arquivo exportado do DW não selecionado")
                    activities = load_dw_export(dw_file)
                elif source_kind == "sql":
                    valid = [r for r in records if not r.issues]
                    activities = query_dw(self.config["sql"], {r.matricula for r in valid}, min(r.activity_date for r in valid), max(r.activity_date for r in valid), password) if valid else []
                    coverage = Coverage(True, min(r.activity_date for r in valid), max(r.activity_date for r in valid), "Consulta SQL para as solicitações válidas") if valid else Coverage()
                else: raise ValueError("Fonte de verificação inválida")
                failed = None
            except Exception as exc:
                # Do not log the driver exception: it can contain connection details.
                activities, failed = [], "falha na consulta/carregamento do DW"; summary.status = "Concluído com pendências"; issues.append(["DW", source_label, failed]); self.logger.error("Falha no DW; detalhes de conexão foram omitidos do log.")
        self.progress("Verificando conflitos", 75, None); details = check_conflicts(records, activities, coverage, failed)
        summary.conflicts = sum(r.result_message.startswith("Conflito") for r in records); summary.no_conflicts = sum(r.result_message == "Sem conflito." for r in records); summary.not_verified = len(records) - summary.conflicts - summary.no_conflicts; summary.conflict_occurrences = len(details)
        if issues or summary.not_verified: summary.status = "Concluído com pendências"
        self.progress("Gerando relatório", 90, None); output = export_report(output_dir, summary, records, details, file_rows, issues)
        self.last_summary = summary
        self.progress("Finalizando", 100, output.name); self.logger.info("Relatório gerado: %s", output); return output
