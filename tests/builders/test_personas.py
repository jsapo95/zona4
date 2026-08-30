"""Regresión: Fix D (hallazgo C5 de la auditoría semántica 2026-08-29).

`build_nietx_protagonistas` completaba `ADN` con el literal `"SÍ"` cuando la
fuente no traía fecha de confirmación genética, afirmando una identificación
falsa para nietxs que la fuente marca como en búsqueda, no nacidxs o
asesinadxs. Este archivo fija:

1. Que `ADN` queda en `"DESCONOCIDA"` -no `"SÍ"`- cuando `restituido.ADN` está
   ausente, y que se persiste la fecha real cuando la fuente la trae.
2. Que `estado` (antes no persistido) se agrega tal como lo da la fuente.
3. Los conteos exactos sobre la fuente real `nietos_y_nietas.json`.
"""
from __future__ import annotations

from collections import Counter

from zona4_graph_loader.builders.personas import build_nietx_protagonistas
from zona4_graph_loader.io.files import NIETXS_PATH, read_json


def _persona_por_id(personas, id_nietx):
    key = f"nietx:{id_nietx}"
    return next(p for p in personas if p["persona_key"] == key)


def test_adn_queda_desconocida_cuando_la_fuente_no_trae_fecha():
    data = [
        {
            "id_nietx": 155,
            "estado": "No nacidx",
            "nombre_completo": "Rodríguez - Vaccarini",
            "restituido": {},
        }
    ]
    resultado = build_nietx_protagonistas(data)
    persona = resultado["personas"][0]
    assert persona["ADN"] == "DESCONOCIDA"
    assert persona["estado"] == "No nacidx"


def test_adn_persiste_la_fecha_real_cuando_la_fuente_la_trae():
    data = [
        {
            "id_nietx": 292,
            "estado": "Restituido/a",
            "nombre_completo": "Juan Cabandié Alfonsín",
            "restituido": {"ADN": "26 de enero, 2004"},
        }
    ]
    resultado = build_nietx_protagonistas(data)
    persona = resultado["personas"][0]
    assert persona["ADN"] == "26 de enero, 2004"
    assert persona["estado"] == "Restituido/a"


def test_restituido_sin_fecha_de_adn_tambien_queda_desconocida_no_si():
    # 35 de los 392 registros reales están en este caso exacto: `estado` =
    # "Restituido/a" pero `restituido` no trae "ADN". No hay que inferir
    # "SÍ" a partir de `estado`; sólo el valor explícito de `restituido.ADN`
    # cuenta como confirmación.
    data = [
        {
            "id_nietx": 999,
            "estado": "Restituido/a",
            "nombre_completo": "Alguien Restituido",
            "restituido": {"Restitución": "1 de enero, 2020"},
        }
    ]
    resultado = build_nietx_protagonistas(data)
    persona = resultado["personas"][0]
    assert persona["ADN"] == "DESCONOCIDA"
    assert persona["estado"] == "Restituido/a"


def test_estado_ausente_en_la_fuente_no_inventa_un_valor():
    data = [{"id_nietx": 1, "nombre_completo": "X - Y", "restituido": {}}]
    resultado = build_nietx_protagonistas(data)
    persona = resultado["personas"][0]
    assert persona["estado"] == "DESCONOCIDA"


def test_sobre_el_archivo_real_los_conteos_coinciden_con_la_auditoria():
    data = read_json(NIETXS_PATH)
    assert len(data) == 392

    resultado = build_nietx_protagonistas(data)
    personas = resultado["personas"]
    assert len(personas) == 392

    adn_confirmado = sum(1 for p in personas if p["ADN"] != "DESCONOCIDA")
    adn_desconocida = sum(1 for p in personas if p["ADN"] == "DESCONOCIDA")
    assert adn_confirmado == 82
    assert adn_desconocida == 310

    # Antes del fix, estos 310 nodos afirmaban ADN:"SÍ" -una confirmación de
    # ADN que la fuente nunca dio. Ninguno debe seguir afirmándola.
    assert all(p["ADN"] != "SÍ" for p in personas)

    distribucion_estado = Counter(p["estado"] for p in personas)
    assert distribucion_estado == Counter(
        {
            "Búsqueda": 252,
            "Restituido/a": 117,
            "No nacidx": 19,
            "Asesinadx": 4,
        }
    )

    # Los 275 nodos que la auditoría marca como afirmando una confirmación
    # falsa (Búsqueda + No nacidx + Asesinadx) deben quedar en DESCONOCIDA.
    afirmaban_falso = [
        p
        for p in personas
        if _estado_de(data, p["persona_key"]) in {"Búsqueda", "No nacidx", "Asesinadx"}
    ]
    assert len(afirmaban_falso) == 275
    assert all(p["ADN"] == "DESCONOCIDA" for p in afirmaban_falso)


def _estado_de(data, persona_key):
    id_nietx = int(persona_key.split(":", 1)[1])
    item = next(i for i in data if i.get("id_nietx") == id_nietx)
    return item.get("estado")
