from __future__ import annotations

import re
from calendar import monthrange
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


def parse_partial_ymd(value: Optional[str]) -> tuple[Optional[str], Optional[str], Optional[str]]:
    if not value:
        return (None, None, None)

    text = value.strip()
    m_day = re.fullmatch(r"(\d{4})/(\d{2})/(\d{2})", text)
    if m_day:
        year, month, day = map(int, m_day.groups())
        try:
            iso = date(year, month, day).isoformat()
            return (iso, iso, "DAY")
        except ValueError:
            return (None, None, None)

    m_month = re.fullmatch(r"(\d{4})/(\d{2})", text)
    if m_month:
        year, month = map(int, m_month.groups())
        if month < 1 or month > 12:
            return (None, None, None)
        start = date(year, month, 1)
        end = date(year, month, monthrange(year, month)[1])
        return (start.isoformat(), end.isoformat(), "MONTH")

    m_year = re.fullmatch(r"(\d{4})", text)
    if m_year:
        year = int(m_year.group(1))
        return (date(year, 1, 1).isoformat(), date(year, 12, 31).isoformat(), "YEAR")

    return (None, None, None)
