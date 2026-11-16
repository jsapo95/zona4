"""Regresión: un país extranjero nombrado con detalle extra cae en Argentina.

Contexto del defecto: `_resolve_foreign_place` sólo reconocía el país cuando
el texto ERA el país ("URUGUAY") o TERMINABA en él con 7 palabras o menos
("MONTEVIDEO URUGUAY"). Si después del país venía una aclaración ("Canelones,
Uruguay. Cruce Ruta 9 y Ruta 70") o la cadena era más larga ("Hotel Ermitage,
Juan Benito Blanco 783 (Pocitos, Montevideo, Uruguay)"), el texto seguía al
gazetteer de Georef, que matcheaba el departamento homónimo "Uruguay" de Entre
Ríos. En `parque_de_la_memoria.json` eso ubicaba en Entre Ríos 5 asesinatos y
1 secuestro ocurridos en Uruguay.

El mismo patrón, medido sobre los 4.224 textos de lugar reales, aparece una
vez más con otro país: "SANTIAGO. CHILE (Bascuñan y Antofagasta, Santiago)"
quedaba como INDETERMINADO en vez de colgar de Chile.

Este archivo fija que esos textos cuelgan del país que nombran, y que la regla
nueva no se lleva calles argentinas con nombre de país ("Uruguay" en San
Nicolás, CABA) ni el departamento Uruguay de Entre Ríos cuando la fuente nombra
la provincia.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from zona4_graph_loader.domain.place_norm import resolve_place


REPO_ROOT = Path(__file__).resolve().parents[2]
GEOREF_CATALOG = REPO_ROOT / "data" / "processed" / "georef_catalog.json"

URUGUAY_KEY = "lugar:PAIS:uruguay"
CHILE_KEY = "lugar:PAIS:chile"

# Valores reales de `parque_de_la_memoria.json` (lugar de asesinato y de
# secuestro) que antes de este fix terminaban en
# `lugar:DEPARTAMENTO:uruguay|lugar:PROVINCIA:entre_rios|lugar:PAIS:argentina`,
# con la ciudad que la propia fuente nombra antes del país.
CASOS_PAIS_CON_DETALLE = [
    ("Canelones - Uruguay. Cruce Ruta N°9 y 70", f"lugar:CIUDAD:canelones|{URUGUAY_KEY}"),
    ("Canelones, Uruguay. Cruce Ruta 9 y Ruta 70", f"lugar:CIUDAD:canelones|{URUGUAY_KEY}"),
    (
        "Montevideo, Uruguay. Aeropuerto Internacional de Carrasco",
        f"lugar:CIUDAD:montevideo|{URUGUAY_KEY}",
    ),
    (
        "Hotel Ermitage, Juan Benito Blanco 783  (Pocitos, Montevideo, Uruguay)",
        f"lugar:CIUDAD:montevideo|{URUGUAY_KEY}",
    ),
    (
        "SANTIAGO. CHILE (Bascuñan y Antofagasta, Santiago)",
        f"lugar:CIUDAD:santiago|{CHILE_KEY}",
    ),
]

# Con Georef se ejercita el camino real de la carga (el que matcheaba el
# departamento homónimo). El catálogo se busca desde la raíz del repo: si no
# se encuentra, `resolve_place` lo ignora en silencio y el caso no probaría
# nada.
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
@pytest.mark.parametrize("raw,esperada", CASOS_PAIS_CON_DETALLE)
def test_pais_con_detalle_cuelga_del_pais(raw: str, esperada: str, use_georef: bool) -> None:
    place = resolve_place(raw, use_georef=use_georef, georef_catalog_path=GEOREF_CATALOG)

    assert place is not None
    assert place["lugar_key"] == esperada
    assert place["tipo"] == "CIUDAD"
    assert "entre_rios" not in place["lugar_key"]


@pytest.mark.parametrize("use_georef", GEOREF_MODES)
def test_pais_seguido_de_direccion_cuelga_solo_del_pais(use_georef: bool) -> None:
    # Si lo que la fuente pone antes del país es una dirección (tiene
    # números), no se inventa una ciudad: se afirma sólo el país.
    place = resolve_place(
        "Juan Benito Blanco 783, Uruguay. Frente al hotel",
        use_georef=use_georef,
        georef_catalog_path=GEOREF_CATALOG,
    )

    assert place is not None
    assert place["lugar_key"] == URUGUAY_KEY
    assert place["tipo"] == "PAIS"


@pytest.mark.skipif(not GEOREF_CATALOG.exists(), reason="falta data/processed/georef_catalog.json")
@pytest.mark.parametrize(
    "raw,esperada",
    [
        # CCD real (ubicación RUVTE): acá "URUGUAY" es el departamento de
        # Entre Ríos y la fuente nombra la provincia.
        (
            "SUIPACHA 1500  ·  CONCEPCIÓN DEL URUGUAY · URUGUAY · ENTRE RÍOS",
            "lugar:CIUDAD:concepcion_del_uruguay|lugar:DEPARTAMENTO:uruguay"
            "|lugar:PROVINCIA:entre_rios|lugar:PAIS:argentina",
        ),
        # Secuestro real: "Uruguay" es la calle (y la estación de subte) de
        # San Nicolás, CABA.
        (
            "CAPITAL FEDERAL (San Nicolas (estación subte B, Uruguay))",
            "lugar:CIUDAD:ciudad_autonoma_de_buenos_aires"
            "|lugar:PROVINCIA:ciudad_autonoma_de_buenos_aires|lugar:PAIS:argentina",
        ),
    ],
)
def test_pais_homonimo_en_contexto_argentino_no_cambia(raw: str, esperada: str) -> None:
    place = resolve_place(raw, use_georef=True, georef_catalog_path=GEOREF_CATALOG)

    assert place is not None
    assert place["lugar_key"] == esperada
