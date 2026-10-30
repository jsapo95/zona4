"""Regresión: CABA duplicada y huérfana (validación 5.2/5.3).

Contexto del defecto: `EQUIV_CITIES` y `_resolve_caba` armaban la clave de
CABA sin padre (`lugar:CIUDAD:ciudad_autonoma_de_buenos_aires`). Ese nodo
quedaba desconectado de ARGENTINA y duplicaba al nodo CIUDAD que sí cuelga de
`lugar:PROVINCIA:ciudad_autonoma_de_buenos_aires`. En la carga del 2026-10-28
tenía 2.386 hechos de detalles_personas (1.801 SECUESTRADO_EN, 377 NACIO_EN,
208 ASESINADO_EN), 400 alias, 6 CCD y 79 direcciones de CCD, todos invisibles
para cualquier roll-up por provincia.

Este archivo fija que esos dos caminos producen la clave anclada en su
provincia, y que el builder arma la cadena CIUDAD -> PROVINCIA -> PAIS.

Fuera de alcance: variantes que hoy no llegan a ninguno de los dos caminos
("C.A.B.A.", "Cap. Federal", "Capital Fed.") y siguen mal resueltas igual
que antes de este fix. Tampoco se fijan "CAPITAL" ni "FEDERAL" sueltos: están
en `EQUIV_CITIES` desde antes, pero son ambiguos ("Federal" es un
departamento de Entre Ríos) y no aparecen en los datos actuales.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from zona4_graph_loader.builders.lugares import build_lugar_layer_rows
from zona4_graph_loader.domain.place_norm import resolve_place


REPO_ROOT = Path(__file__).resolve().parents[2]
GEOREF_CATALOG = REPO_ROOT / "data" / "processed" / "georef_catalog.json"

PAIS_KEY = "lugar:PAIS:argentina"
CABA_PROVINCIA_KEY = f"lugar:PROVINCIA:ciudad_autonoma_de_buenos_aires|{PAIS_KEY}"
CABA_CIUDAD_KEY = f"lugar:CIUDAD:ciudad_autonoma_de_buenos_aires|{CABA_PROVINCIA_KEY}"
CABA_HUERFANA_KEY = "lugar:CIUDAD:ciudad_autonoma_de_buenos_aires"


# Valores que entran por la rama EQUIV_CITIES de `resolve_place`.
EQUIV_VALUES = [
    "Capital Federal",
    "CAPITAL FEDERAL",
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

# Con Georef se ejercita el camino real de la carga. El catálogo se busca
# desde la raíz del repo, no desde el directorio actual: si no se encuentra,
# `resolve_place` lo ignora en silencio y el caso no probaría nada.
GEOREF_MODES = [
    False,
    pytest.param(
        True,
        marks=pytest.mark.skipif(
            not GEOREF_CATALOG.exists(), reason="falta data/processed/georef_catalog.json"
        ),
    ),
]


@pytest.mark.parametrize("use_georef", GEOREF_MODES)
@pytest.mark.parametrize("raw", EQUIV_VALUES + FALLBACK_VALUES)
def test_caba_generica_cuelga_de_su_provincia(raw: str, use_georef: bool) -> None:
    place = resolve_place(raw, use_georef=use_georef, georef_catalog_path=GEOREF_CATALOG)

    assert place is not None
    assert place["lugar_key"] == CABA_CIUDAD_KEY
    assert place["parent_key"] == CABA_PROVINCIA_KEY
    assert place["tipo"] == "CIUDAD"


def test_builder_arma_la_cadena_ciudad_provincia_pais() -> None:
    data = [
        {"registro": 1, "detalle": {"descripcion_lugar_de_secuestro": "Capital Federal"}},
        {"registro": 2, "detalle": {"descripcion_lugar_de_secuestro": FALLBACK_VALUES[0]}},
    ]
    rows = build_lugar_layer_rows(
        data,
        use_georef=False,
        georef_catalog_path=GEOREF_CATALOG,
        georef_min_score=0.76,
        georef_ambiguity_delta=0.02,
    )

    lugar_keys = {row["lugar_key"] for row in rows["lugares"] if "alias_key" not in row}
    assert CABA_CIUDAD_KEY in lugar_keys
    assert CABA_HUERFANA_KEY not in lugar_keys

    parte_de = {
        (row["child_key"], row["parent_key"])
        for row in rows["jerarquias"]
        if row.get("tipo_relacion") == "PARTE_DE"
    }
    assert (CABA_CIUDAD_KEY, CABA_PROVINCIA_KEY) in parte_de
    assert (CABA_PROVINCIA_KEY, PAIS_KEY) in parte_de

    secuestros = [e for e in rows["eventos_espaciales"] if e["tipo_relacion"] == "SECUESTRADO_EN"]
    assert len(secuestros) == 2
    assert {e["lugar_key"] for e in secuestros} == {CABA_CIUDAD_KEY}
