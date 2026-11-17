from __future__ import annotations

from openpyxl.utils import column_index_from_string

from .models import Profile
from .normalize import normalized_header

REQUIRED = ("matricula", "data")
OPTIONAL_SCHEDULE_FIELDS = ("inicio", "fim")


def resolve_profile_sheet(workbook, profile: Profile) -> tuple[object, dict[str, int]]:
    candidates = [workbook[name] for name in profile.sheet_names if name in workbook.sheetnames] if profile.sheet_names else list(workbook.worksheets)
    matches = []
    for sheet in candidates:
        header_cells = next(sheet.iter_rows(min_row=profile.header_row, max_row=profile.header_row), ())
        headers: dict[str, set[int]] = {}
        for cell in header_cells:
            if cell.value is not None:
                headers.setdefault(normalized_header(cell.value), set()).add(cell.column)
        resolved: dict[str, int] = {}
        valid = True
        for field in REQUIRED:
            spec = profile.fields.get(field, {})
            aliases = [normalized_header(alias) for alias in spec.get("aliases", [])]
            alias_columns = {column for alias in aliases for column in headers.get(alias, set())}
            if len(alias_columns) > 1:
                valid = False
                break
            if alias_columns:
                resolved[field] = alias_columns.pop()
            elif spec.get("column"):
                resolved[field] = column_index_from_string(spec["column"])
                if resolved[field] > sheet.max_column:
                    valid = False
                    break
                if aliases and normalized_header(header_cells[resolved[field] - 1].value) not in aliases:
                    valid = False
                    break
            else:
                valid = False
                break
        if valid:
            for field in OPTIONAL_SCHEDULE_FIELDS:
                spec = profile.fields.get(field, {})
                aliases = [normalized_header(alias) for alias in spec.get("aliases", [])]
                alias_columns = {column for alias in aliases for column in headers.get(alias, set())}
                if len(alias_columns) > 1:
                    valid = False
                    break
                if len(alias_columns) == 1:
                    resolved[field] = alias_columns.pop()
                elif spec.get("column"):
                    column = column_index_from_string(spec["column"])
                    if column <= sheet.max_column and (not aliases or normalized_header(header_cells[column - 1].value) in aliases):
                        resolved[field] = column
            if valid:
                matches.append((sheet, resolved))
    if not matches:
        raise ValueError(f"Perfil '{profile.name}' não reconheceu nenhuma aba do arquivo.")
    if len(matches) > 1:
        names = ", ".join(item[0].title for item in matches)
        raise ValueError(f"Perfil '{profile.name}' é ambíguo nas abas: {names}.")
    return matches[0]
