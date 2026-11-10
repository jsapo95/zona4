"""Niveles de comparación por campo (sección 2 del notebook).

Cada función recibe el valor de un campo en dos registros y devuelve el
índice del nivel en `NIVELES[campo]`, o `FALTA` (None) si el campo no está en
alguno de los dos. Los niveles de cada campo son excluyentes y se evalúan en
el orden en que aparecen: el primero que se cumple es el nivel del par.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Dict, FrozenSet, Optional, Tuple

from zona4_graph_loader.domain.name_similarity import _levenshtein_distance, name_token_set

CAMPOS: Tuple[str, ...] = ("apellido", "nombre", "fecha_nacimiento", "fecha_secuestro", "centro")

_NIVELES_TOKENS = ("exacto", "contenido", "errata", "comparte", "distinto")
_NIVELES_FECHA = ("exacta", "dia_mes_invertidos", "mismo_año_mes", "mismo_año", "distinta")

NIVELES: Dict[str, Tuple[str, ...]] = {
    "apellido": _NIVELES_TOKENS,
    "nombre": _NIVELES_TOKENS,
    "fecha_nacimiento": _NIVELES_FECHA,
    "fecha_secuestro": _NIVELES_FECHA,
    "centro": ("comparte", "ninguno_en_comun"),
}

FALTA = None

# Un token de nombre se considera errata de otro sólo si los dos tienen al
# menos este largo: entre tokens cortos ("li"/"lu") una letra de diferencia ya
# es otro nombre.
LARGO_MINIMO_ERRATA = 4

Tokens = FrozenSet[str]


@dataclass(frozen=True)
class Fecha:
    """Fecha con la precisión que trae la fuente: año, año y mes, o completa."""

    año: int
    mes: Optional[int] = None
    dia: Optional[int] = None


_FECHA = re.compile(r"^(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?$")


def parsear_fecha(valor: Optional[str]) -> Optional[Fecha]:
    """`AAAA`, `AAAA-MM` o `AAAA-MM-DD` que sea una fecha del calendario.
    Cualquier otra cosa (centinelas como "DESCONOCIDA", texto libre, un mes 13
    o un 30 de febrero) es un faltante."""
    if not valor:
        return None
    match = _FECHA.match(valor.strip())
    if not match:
        return None
    año, mes, dia = (int(x) if x else None for x in match.groups())
    try:
        date(año, 1 if mes is None else mes, 1 if dia is None else dia)
    except ValueError:
        return None
    return Fecha(año, mes, dia)


def separar_nombre(nombre: Optional[str]) -> Tuple[Optional[Tokens], Optional[Tokens]]:
    """Separa "Apellido(s), Nombre(s)" en dos conjuntos de tokens.

    Sin coma no hay forma segura de saber qué es apellido: los dos campos
    quedan faltantes. Los tokens son los de `name_token_set`, el mismo
    normalizador que usa la resolución de identidades (sin acentos, sin
    partículas como "de", sin iniciales de una letra).
    """
    if not nombre or "," not in nombre:
        return None, None
    apellido, _, nombres = nombre.partition(",")
    tokens_apellido = frozenset(name_token_set(apellido))
    tokens_nombre = frozenset(name_token_set(nombres))
    return tokens_apellido or None, tokens_nombre or None


def son_errata(a: str, b: str) -> bool:
    """Dos tokens distintos, de al menos `LARGO_MINIMO_ERRATA` letras, a
    distancia de Levenshtein 1 (una letra agregada, quitada o cambiada)."""
    return (
        a != b
        and len(a) >= LARGO_MINIMO_ERRATA
        and len(b) >= LARGO_MINIMO_ERRATA
        and _levenshtein_distance(a, b) == 1
    )


def _corregir_erratas(origen: Tokens, destino: Tokens) -> Tokens:
    """Reemplaza cada token de `origen` que no está en `destino` por el primer
    token de `destino` (en orden alfabético) del que es errata."""
    corregidos = set()
    for token in origen:
        if token not in destino:
            for candidato in sorted(destino):
                if son_errata(token, candidato):
                    token = candidato
                    break
        corregidos.add(token)
    return frozenset(corregidos)


def nivel_tokens(a: Optional[Tokens], b: Optional[Tokens]) -> Optional[int]:
    """Nivel de apellido o de nombre de pila."""
    if not a or not b:
        return FALTA
    if a == b:
        return 0  # exacto
    if a < b or b < a:
        return 1  # contenido: uno tiene tokens de más
    a_corregido = _corregir_erratas(a, b)
    b_corregido = _corregir_erratas(b, a)
    if a_corregido <= b or b <= a_corregido or b_corregido <= a or a <= b_corregido:
        return 2  # errata
    if a_corregido & b or b_corregido & a:
        return 3  # comparte: algún token en común, exacto o tras corregir erratas
    return 4  # distinto


def nivel_fecha(a: Optional[Fecha], b: Optional[Fecha]) -> Optional[int]:
    """Nivel de una fecha (nacimiento o secuestro).

    Se compara con la precisión que tengan los dos: si uno sólo trae el año,
    el mejor nivel posible es "mismo_año".
    """
    if a is None or b is None:
        return FALTA
    if a.año != b.año:
        return 4  # distinta
    if a.mes is None or b.mes is None:
        return 3  # mismo_año
    completas = a.dia is not None and b.dia is not None
    if completas and a == b:
        return 0  # exacta
    if completas and a.mes == b.dia and a.dia == b.mes:
        return 1  # dia_mes_invertidos
    if a.mes == b.mes:
        return 2  # mismo_año_mes
    return 3  # mismo_año


def nivel_centro(a: Optional[FrozenSet[str]], b: Optional[FrozenSet[str]]) -> Optional[int]:
    """¿Pasaron por algún centro clandestino en común (`PRESENTE_EN`)?"""
    if not a or not b:
        return FALTA
    return 0 if a & b else 1
