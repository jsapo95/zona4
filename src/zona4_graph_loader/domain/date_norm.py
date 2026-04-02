from __future__ import annotations

import re
from datetime import date
from typing import Optional

from zona4_graph_loader.constants import SPANISH_MONTHS
from zona4_graph_loader.domain.text_norm import strip_accents


def parse_ddmmyyyy(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    match = re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", value.strip())
    if not match:
        return None
    day, month, year = map(int, match.groups())
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def parse_spanish_long_date(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    text = strip_accents(value.lower().strip())
    match = re.fullmatch(r"(\d{1,2})\s+de\s+([a-z]+),\s*(\d{4})", text)
    if not match:
        return None
    day = int(match.group(1))
    month_name = match.group(2)
    year = int(match.group(3))
    month = SPANISH_MONTHS.get(month_name)
    if not month:
        return None
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None
