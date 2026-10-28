from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .models import Profile, SourceFolder


def application_root() -> Path:
    return Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent


def default_config_path() -> Path:
    return application_root() / "config.json"


def load_config(path: Path | None = None) -> dict[str, Any]:
    path = path or default_config_path()
    example = application_root() / "config.example.json"
    source = path if path.exists() else example
    if not source.exists():
        raise FileNotFoundError(f"Configuração não encontrada: {source}")
    return json.loads(source.read_text(encoding="utf-8"))


def save_config(config: dict[str, Any], path: Path | None = None) -> None:
    path = path or default_config_path()
    path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


def source_folders(config: dict[str, Any]) -> list[SourceFolder]:
    return [SourceFolder(**item) for item in config.get("source_folders", [])]


def profiles(config: dict[str, Any]) -> list[Profile]:
    return [Profile(**item) for item in config.get("profiles", [])]
