from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from .conflicts import check_conflicts
from .discovery import discover_excel_files, output_is_safe, validate_input_directory
from .dw import load_dw_export
from .exporter import export_report
from .models import CancelledError, CancellationToken, Coverage, RunSummary
from .profiles import Profile
from .reader import read_requests


class Processor:
    def __init__(self, config: dict, logger: logging.Logger, progress=lambda *_: None):
        self.config, self.logger, self.progress = config, logger, progress
        self.last_summary = None

    def _stage(self, name: str, percentage: int | None = None, current: str | None = None) -> None:
        suffix = f" — {current}" if current else ""
        self.logger.info("%s%s", name, suffix)
        self.progress(name, percentage, current)

    def validate(self, input_dir: Path):
        from .config import source_folders
        return validate_input_directory(input_dir, source_folders(self.config))

    def run(self, input_dir: Path, output_dir: Path, profile: Profile, source_kind: str, dw_file: Path | None, coverage: Coverage | None, token: CancellationToken, password: str | None = None) -> Path:
        from .config import source_folders
        execution_id = str(uuid4()); started = datetime.now().isoformat(timespec="seconds")
        source_label = "Somente consolidação" if source_kind == "none" else f"Arquivo exportado da view: {dw_file.name if dw_file else 'não selecionado'}"
        summary = RunSummary(execution_id, started, source_label)
        folders = source_folders(self.config)
        if not output_is_safe(output_dir, input_dir, folders): raise ValueError("A pasta de saída não pode ficar dentro de uma pasta de origem habilitada.")
        self._stage("Validando configurações"); found, missing = self.validate(input_dir)
        if not found: raise ValueError("Nenhuma pasta de origem habilitada foi encontrada.")
        issues = [["Pasta ausente", folder.name, "Pasta habilitada não encontrada"] for folder in missing]
        file_rows, records = [], []
        self._stage("Localizando arquivos")
        work = []
        for folder, path in found:
            eligible, ignored = discover_excel_files(path); summary.files_found += len(eligible)
            for item in ignored: file_rows.append([folder.request_type, folder.name, item.name, "Ignorado", "Temporário ou formato não suportado"])
            if not eligible: issues.append(["Pasta sem arquivo", folder.name, "Nenhum arquivo disponível para processamento"])
            work.extend((folder, item) for item in eligible)
        if not work: raise ValueError("Nenhum arquivo Excel elegível foi encontrado nas pastas disponíveis.")
        for index, (folder, file) in enumerate(work, 1):
            token.raise_if_cancelled(); self._stage("Lendo solicitações", 5 + int(index / len(work) * 45), file.name)
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
            try:
                if source_kind == "file":
                    if not dw_file: raise ValueError("Arquivo exportado da view não selecionado")
                    wanted_keys = {(record.matricula, record.activity_date) for record in records if not record.issues}
                    if not wanted_keys:
                        self._stage("Arquivo da view não será carregado", 70, "não há Evento Avulso válido para comparar")
                        activities = []
                    else:
                        self._stage("Carregando arquivo exportado da view", 55, dw_file.name)
                        activities = load_dw_export(dw_file, token, lambda done, total: self._stage("Carregando arquivo exportado da view", 55 + int(done / total * 15) if total else 70, f"{done:,} de {total:,} linhas"), wanted_keys)
                else: raise ValueError("Fonte de verificação inválida")
                failed = None
            except CancelledError:
                self.logger.info("Cancelamento confirmado durante a leitura do arquivo da view.")
                raise
            except Exception as exc:
                # Do not log the driver exception: it can contain connection details.
                activities, failed = [], "falha na consulta/carregamento do DW"; summary.status = "Concluído com pendências"; issues.append(["DW", source_label, failed]); self.logger.error("Falha no DW; detalhes de conexão foram omitidos do log.")
        self._stage("Verificando conflitos", 75); token.raise_if_cancelled(); details = check_conflicts(records, activities, coverage, failed)
        summary.conflicts = sum(r.result_message.startswith("Conflito") for r in records); summary.no_conflicts = sum(r.result_message == "Sem conflito." for r in records); summary.not_verified = len(records) - summary.conflicts - summary.no_conflicts; summary.conflict_occurrences = len(details)
        if issues or summary.not_verified: summary.status = "Concluído com pendências"
        self._stage("Gerando relatório", 90); token.raise_if_cancelled(); output = export_report(output_dir, summary, records, details, file_rows, issues)
        self.last_summary = summary
        self._stage("Finalizando", 100, output.name); self.logger.info("Relatório gerado: %s", output); return output
