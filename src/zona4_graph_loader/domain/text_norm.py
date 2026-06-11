from __future__ import annotations

import re
import unicodedata
from typing import Any, Optional


def norm_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def strip_accents(value: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", value) if not unicodedata.combining(c))


def slugify_name(value: str) -> str:
    text = strip_accents(value.lower())
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = norm_space(text)
    return text.replace(" ", "_")


def clean_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    value = norm_space(value)
    if value in {"", "-", "No hay informacion."}:
        return None
    return value


def persona_key_from_name(name: str) -> str:
    return f"nombre:{slugify_name(name)}"
