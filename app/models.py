from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time
from pathlib import Path
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
    request_types: list[str]
    fields: dict[str, dict[str, Any]]


@dataclass
class RequestRecord:
    values: dict[str, Any]
    request_type: str
    matricula: str | None
    activity_date: date | None
    start_time: time | None
    end_time: time | None
    source_file: str
    relative_path: str
    source_sheet: str
    source_row: int
    source_folder: str
    profile_id: str
    record_id: str
    execution_id: str
    issues: list[str] = field(default_factory=list)
    result_type: str = ""
    result_message: str = ""
    conflict_count: int = 0


@dataclass(frozen=True)
class DwActivity:
    matricula: str | None
    activity_date: date | None
    start_time: time | None
    end_time: time | None
    activity_type: str | None
    description: str | None
    source_row: int | None = None
    issues: tuple[str, ...] = ()


@dataclass(frozen=True)
class ConflictDetail:
    request_id: str
    request_type: str
    matricula: str
    activity_date: date
    event_start: time
    event_end: time
    dw_start: time
    dw_end: time
    dw_type: str
    dw_description: str


@dataclass
class Coverage:
    confirmed: bool = False
    start: date | None = None
    end: date | None = None
    description: str = ""

    def contains(self, value: date | None) -> bool:
        return bool(self.confirmed and value and self.start and self.end and self.start <= value <= self.end)


@dataclass
class RunSummary:
    execution_id: str
    started_at: str
    source_label: str
    status: str = "Concluído"
    files_found: int = 0
    files_processed: int = 0
    files_with_error: int = 0
    letivas: int = 0
    nao_letivas: int = 0
    conflicts: int = 0
    no_conflicts: int = 0
    not_verified: int = 0
    conflict_occurrences: int = 0
    notes: list[str] = field(default_factory=list)


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
