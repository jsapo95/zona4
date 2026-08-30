from __future__ import annotations

import re
from calendar import monthrange
from datetime import date
from typing import Optional

from zona4_graph_loader.constants import SPANISH_MONTHS
from zona4_graph_loader.domain.text_norm import strip_accents


# Fix E (auditoría 2026-08-29, hallazgo I6): fechas imposibles pasadas sin
# validación (7 NACIO_EN entre 2021 y 2052, 12 fecha_secuestro entre 1997 y
# 2077, 1 fecha_nacimiento en 2010 para un represor nacido en 1925). Los
# límites de abajo no son arbitrarios: son el rango real, verificado sobre
# los datos crudos actuales, de las decenas de miles de fechas que SÍ
# parsean bien para estos mismos campos en estas mismas fuentes
# (`descripcion_fecha_de_secuestro`: 1970-1983; `descripcion_fecha_de_asesinato`:
# 1969-1983; fechas de nacimiento de víctimas e imputados: 1894-1979), con
# margen adicional para no rozar ese rango observado. Cualquier valor fuera
# de este margen es, con altísima probabilidad, una errata de tipeo en la
# fuente (año traspuesto, dígito de más) y no un caso real: no se corrige
# -sería inventar el dato que la fuente no da con certeza-, se descarta.
_FECHA_HECHO_MIN = date(1966, 1, 1)
_FECHA_HECHO_MAX = date(1990, 12, 31)
_FECHA_NACIMIENTO_MAX = date(1983, 12, 31)


def _dentro_de_rango(iso: Optional[str], minimo: Optional[date], maximo: Optional[date]) -> Optional[str]:
    if not iso:
        return iso
    try:
        valor = date.fromisoformat(iso)
    except ValueError:
        return iso
    if minimo is not None and valor < minimo:
        return None
    if maximo is not None and valor > maximo:
        return None
    return iso


def validar_fecha_de_hecho(iso: Optional[str]) -> Optional[str]:
    """Para fechas de secuestro/asesinato: rechaza (devuelve None) cualquier
    valor fuera de [1966, 1990]. Ver nota de módulo para la justificación
    del rango.
    """
    return _dentro_de_rango(iso, _FECHA_HECHO_MIN, _FECHA_HECHO_MAX)


def validar_fecha_de_nacimiento(iso: Optional[str]) -> Optional[str]:
    """Para fechas de nacimiento: rechaza (devuelve None) cualquier valor
    posterior a 1983. Sin cota inferior: no hay evidencia en la auditoría de
    nacimientos demasiado tempranos, sólo de nacimientos fabricados en el
    futuro (2021-2052).
    """
    return _dentro_de_rango(iso, None, _FECHA_NACIMIENTO_MAX)


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
