from __future__ import annotations

import re
import unicodedata
from typing import Any


def normalized_header(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ASCII", "ignore").decode().lower()
    return re.sub(r"\s+", " ", text).strip()


def safe_text(value: Any) -> Any:
    """Prevents user-supplied strings from becoming formulas in the export."""
    return "'" + value if isinstance(value, str) and value.startswith("=") else value
