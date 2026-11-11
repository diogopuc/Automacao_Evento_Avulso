from __future__ import annotations

from dataclasses import dataclass
from threading import Event
from typing import Any


@dataclass(frozen=True)
class SourceFolder:
    name: str
    request_type: str
    enabled: bool = True


@dataclass
class Profile:
    id: str
    name: str
    sheet_names: list[str]
    header_row: int
    first_data_row: int
    fields: dict[str, dict[str, Any]]


@dataclass
class RequestRecord:
    values: dict[str, Any]
    request_type: str


@dataclass
class RunSummary:
    execution_id: str
    started_at: str
    status: str = "Concluído"
    files_found: int = 0
    files_processed: int = 0
    files_with_error: int = 0
    letivas: int = 0
    nao_letivas: int = 0


class CancelledError(Exception):
    pass


class CancellationToken:
    def __init__(self) -> None:
        self._event = Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        if self._event.is_set():
            raise CancelledError("Execução cancelada pelo usuário.")
