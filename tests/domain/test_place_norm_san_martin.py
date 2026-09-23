"""Regresión: topónimos de San Martín mal georresueltos (Task 14).

Contexto del defecto: sobre los 303 registros de
`data/raw/archivo_memoria_san_martin.json` (fuente centrada en el partido de
General San Martín, Buenos Aires), `resolve_place` ubicaba 60 víctimas en
provincias equivocadas:

- "José León Suárez" (34) -> Jujuy (Dr. Manuel Belgrano) vía
  `_resolve_segmented_place`.
- "San Andrés" (13) -> Tucumán (Cruz Alta).
- "Villa Concepción" (13) -> Tucumán (Chicligasta).

Las tres son localidades reales del partido de General San Martín. Este
archivo fija el comportamiento correcto: las tres deben resolver a
PROVINCIA:BUENOS AIRES (nunca a otra provincia).

Nota sobre el alcance del fix: `EQUIV_CITIES` sólo puede anclar un lugar
directamente bajo `lugar:PROVINCIA:<...>` (ver `resolve_place`, rama
`if alias_norm in EQUIV_CITIES`: el tercer elemento de la tupla siempre se
envuelve como `make_lugar_key("PROVINCIA", parent_name, ...)`). No hay forma
de producir desde esa tabla un `parent_key` de tres niveles como
`lugar:DEPARTAMENTO:general_san_martin|lugar:PROVINCIA:buenos_aires|...`
sin tocar la lógica de `resolve_place` (fuera de alcance de esta tarea). Por
eso estas pruebas verifican la provincia correcta (Buenos Aires) y NO la
pertenencia al subárbol de `lugar:DEPARTAMENTO:general_san_martin`, que sólo
alcanzan los 124 registros resueltos directamente vía el gazetteer de Georef.
"""
from __future__ import annotations

import json
from collections import Counter

from zona4_graph_loader.domain.place_norm import resolve_place
from zona4_graph_loader.io.raw_files import read_raw_json


BUENOS_AIRES_PROVINCIA_KEY = "lugar:PROVINCIA:buenos_aires|lugar:PAIS:argentina"
GENERAL_SAN_MARTIN_DEPARTAMENTO_KEY = (
    "lugar:DEPARTAMENTO:general_san_martin|lugar:PROVINCIA:buenos_aires|lugar:PAIS:argentina"
)


def test_jose_leon_suarez_resuelve_a_buenos_aires_no_jujuy():
    resuelto = resolve_place("José León Suárez")
    assert resuelto is not None
    assert "jujuy" not in resuelto["lugar_key"]
    assert resuelto["tipo"] == "CIUDAD"
    assert resuelto["nombre_canonico"] == "VILLA JOSE LEON SUAREZ"
    assert resuelto["parent_key"] == BUENOS_AIRES_PROVINCIA_KEY
    assert resuelto["lugar_key"] == (
        "lugar:CIUDAD:villa_jose_leon_suarez|lugar:PROVINCIA:buenos_aires|lugar:PAIS:argentina"
    )


def test_san_andres_resuelve_a_buenos_aires_no_tucuman():
    resuelto = resolve_place("San Andrés")
    assert resuelto is not None
    assert "tucuman" not in resuelto["lugar_key"]
    assert resuelto["tipo"] == "CIUDAD"
    assert resuelto["nombre_canonico"] == "VILLA SAN ANDRES"
    assert resuelto["parent_key"] == BUENOS_AIRES_PROVINCIA_KEY
    assert resuelto["lugar_key"] == (
        "lugar:CIUDAD:villa_san_andres|lugar:PROVINCIA:buenos_aires|lugar:PAIS:argentina"
    )


def test_villa_concepcion_resuelve_a_buenos_aires_no_tucuman():
    resuelto = resolve_place("Villa Concepción")
    assert resuelto is not None
    assert "tucuman" not in resuelto["lugar_key"]
    assert resuelto["tipo"] == "CIUDAD"
    assert resuelto["nombre_canonico"] == "VILLA CONCEPCION"
    assert resuelto["parent_key"] == BUENOS_AIRES_PROVINCIA_KEY
    assert resuelto["lugar_key"] == (
        "lugar:CIUDAD:villa_concepcion|lugar:PROVINCIA:buenos_aires|lugar:PAIS:argentina"
    )


def test_jose_leon_suarez_san_martin_entry_sigue_intacta():
    # La entrada previa ("JOSE LEON SUAREZ SAN MARTIN") no debe tocarse: puede
    # servir a otra fuente cuyo valor crudo sí incluya el sufijo "San Martín".
    resuelto = resolve_place("José León Suárez San Martín")
    assert resuelto is not None
    assert resuelto["nombre_canonico"] == "VILLA JOSE LEON SUAREZ"
    assert resuelto["parent_key"] == BUENOS_AIRES_PROVINCIA_KEY


def test_general_san_martin_departamento_key_es_el_de_los_124_registros_correctos():
    # Confirma la forma exacta del parent_key que ya usan los 124 registros
    # bien resueltos (Villa Ballester, Villa Lynch, Villa Maipú, Billinghurst,
    # Villa Libertad), para dejar constancia de cuál es "el subárbol correcto"
    # que las nuevas entradas de EQUIV_CITIES no pueden alcanzar.
    resuelto = resolve_place("Villa Ballester")
    assert resuelto is not None
    assert resuelto["parent_key"] == GENERAL_SAN_MARTIN_DEPARTAMENTO_KEY


def test_distribucion_sobre_archivo_real_san_martin():
    data = read_raw_json("archivo_memoria_san_martin.json")
    assert len(data) == 303

    bajo_general_san_martin = 0
    bajo_buenos_aires_directo = 0
    otras_provincias = Counter()

    for registro in data:
        resuelto = resolve_place(registro.get("lugar"))
        assert resuelto is not None
        lugar_key = resuelto["lugar_key"]
        if "general_san_martin" in lugar_key:
            bajo_general_san_martin += 1
        elif lugar_key.endswith("lugar:PROVINCIA:buenos_aires|lugar:PAIS:argentina"):
            bajo_buenos_aires_directo += 1
        elif "PROVINCIA:jujuy" in lugar_key.upper() or "jujuy" in lugar_key:
            otras_provincias["jujuy"] += 1
        elif "tucuman" in lugar_key:
            otras_provincias["tucuman"] += 1
        else:
            otras_provincias[lugar_key] += 1

    assert otras_provincias["jujuy"] == 0
    assert otras_provincias["tucuman"] == 0
    assert bajo_general_san_martin == 124
    # 119 preexistentes (heurística "asumir Buenos Aires") + 60 recién
    # corregidos que ahora anclan a PROVINCIA:BUENOS AIRES en lugar de
    # Jujuy/Tucumán.
    assert bajo_buenos_aires_directo == 119 + 60
