"""Regresión: CABA duplicada y huérfana (validación 5.2/5.3).

Contexto del defecto: `EQUIV_CITIES` y `_resolve_caba` armaban la clave de
CABA sin padre (`lugar:CIUDAD:ciudad_autonoma_de_buenos_aires`). Ese nodo
quedaba desconectado de ARGENTINA y duplicaba al nodo CIUDAD que sí cuelga de
`lugar:PROVINCIA:ciudad_autonoma_de_buenos_aires`. En la carga del 2026-10-28
tenía 2.386 hechos de detalles_personas (1.801 SECUESTRADO_EN, 377 NACIO_EN,
208 ASESINADO_EN), 400 alias, 6 CCD y 79 direcciones de CCD, todos invisibles
para cualquier roll-up por provincia.

Este archivo fija que todo camino que resuelve a CABA genérica produce la
clave anclada en su provincia.
"""
from __future__ import annotations

import pytest

from zona4_graph_loader.domain.place_norm import resolve_place


CABA_PROVINCIA_KEY = "lugar:PROVINCIA:ciudad_autonoma_de_buenos_aires|lugar:PAIS:argentina"
CABA_CIUDAD_KEY = f"lugar:CIUDAD:ciudad_autonoma_de_buenos_aires|{CABA_PROVINCIA_KEY}"
CABA_HUERFANA_KEY = "lugar:CIUDAD:ciudad_autonoma_de_buenos_aires"


# Valores que entran por la rama EQUIV_CITIES de `resolve_place`.
EQUIV_VALUES = [
    "CAPITAL",
    "Capital Federal",
    "CAPITAL FEDERAL",
    "Federal",
    "CABA",
    "Ciudad de Bs. As.",
    "Ciudad de Buenos Aires",
]

# Valores reales de detalles_personas (alias del nodo huérfano en la carga del
# 2026-10-28) que no son un barrio resoluble por Georef y caen al fallback
# `_resolve_caba`.
FALLBACK_VALUES = [
    "Capital Federal. Viamonte 2565 3º. Balvanera",
    "Capital Federal. Corrientes 3645 9º F. Almagro",
    "San Juan y Entre Ríos, Capital Federal",
    "Teniente Coronel Gregorio Pomar, CABA",
]


@pytest.mark.parametrize("use_georef", [True, False])
@pytest.mark.parametrize("raw", EQUIV_VALUES + FALLBACK_VALUES)
def test_caba_generica_cuelga_de_su_provincia(raw: str, use_georef: bool) -> None:
    place = resolve_place(raw, use_georef=use_georef)

    assert place is not None
    assert place["lugar_key"] == CABA_CIUDAD_KEY
    assert place["parent_key"] == CABA_PROVINCIA_KEY
    assert place["tipo"] == "CIUDAD"


@pytest.mark.parametrize("raw", EQUIV_VALUES + FALLBACK_VALUES)
def test_caba_nunca_produce_la_clave_huerfana(raw: str) -> None:
    place = resolve_place(raw)

    assert place is not None
    assert place["lugar_key"] != CABA_HUERFANA_KEY
    assert place["parent_key"]
