from __future__ import annotations

from pathlib import Path

from .models import SourceFolder

SUPPORTED_SUFFIXES = {".xlsx", ".xlsm"}


def validate_input_directory(root: Path, folders: list[SourceFolder]) -> tuple[list[tuple[SourceFolder, Path]], list[SourceFolder]]:
    if not root.exists() or not root.is_dir():
        raise ValueError(f"Diretório de entrada indisponível: {root}")
    if not root.stat():
        raise ValueError(f"Não foi possível acessar o diretório: {root}")
    found, missing = [], []
    for folder in folders:
        if not folder.enabled:
            continue
        path = root / folder.name
        if path.is_dir() and not path.is_symlink():
            found.append((folder, path))
        else:
            missing.append(folder)
    return found, missing


def discover_excel_files(folder: Path) -> tuple[list[Path], list[Path]]:
    """Only immediate regular files; no subfolders, symlinks, or Excel lock files."""
    eligible, ignored = [], []
    for item in folder.iterdir():
        if item.is_dir() or item.is_symlink() or not item.is_file():
            continue
        if item.name.startswith("~$") or item.suffix.lower() not in SUPPORTED_SUFFIXES:
            ignored.append(item)
        else:
            eligible.append(item)
    return sorted(eligible), sorted(ignored)


def output_is_safe(output_dir: Path, input_root: Path, folders: list[SourceFolder]) -> bool:
    out = output_dir.resolve()
    for source in folders:
        if source.enabled and (input_root / source.name).exists():
            try:
                out.relative_to((input_root / source.name).resolve())
                return False
            except ValueError:
                pass
    return True
