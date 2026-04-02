from __future__ import annotations

import re
from typing import Optional

from zona4_graph_loader.domain.text_norm import clean_text, strip_accents


def parse_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    text = clean_text(value)
    if text is None:
        return None
    match = re.search(r"\d+", text)
    return int(match.group(0)) if match else None


def normalize_embarazo(value: Optional[str]) -> tuple[str, Optional[int]]:
    text = clean_text(value)
    if text is None:
        return ("NO_INFO", None)
    text_norm = strip_accents(text.lower())
    if text_norm in {"si", "sí"}:
        return ("SI", None)
    months = parse_int(text)
    if months is not None:
        return ("MESES", months)
    return ("OTRO", None)
