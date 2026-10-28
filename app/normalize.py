from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, time
from typing import Any


def normalized_header(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ASCII", "ignore").decode().lower()
    return re.sub(r"\s+", " ", text).strip()


def normalize_id(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    return text or None


def parse_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime): return value.date()
    if isinstance(value, date): return value
    if isinstance(value, str):
        for pattern in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y"):
            try: return datetime.strptime(value.strip(), pattern).date()
            except ValueError: pass
    return None


def parse_time(value: Any) -> time | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime): return value.time().replace(second=0, microsecond=0)
    if isinstance(value, time): return value.replace(second=0, microsecond=0)
    if isinstance(value, str):
        for pattern in ("%H:%M", "%H:%M:%S", "%Hh%M"):
            try: return datetime.strptime(value.strip(), pattern).time()
            except ValueError: pass
    return None


def safe_text(value: Any) -> Any:
    """Prevents user-supplied strings from becoming formulas in the export."""
    return "'" + value if isinstance(value, str) and value.startswith("=") else value


def unique_preserve(values: list[str]) -> list[str]:
    seen = set(); result = []
    for value in values:
        key = normalized_header(value)
        if key and key not in seen:
            seen.add(key); result.append(value)
    return result
