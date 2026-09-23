"""Regresión: Fix E (hallazgo I5 de la auditoría semántica 2026-08-29).

`build_lugar_layer_rows` genera nodos `:DirecciónCCD` a partir de
direcciones extraídas del texto libre de secuestro/nacimiento/asesinato de
una víctima (domicilios, vía pública, lugares de trabajo) -nunca de un
centro clandestino real. Antes de este fix, esos nodos llevaban la misma
label `:DirecciónCCD`, sin ninguna marca, que los que sí vienen de un CCD
real (`builders/ccds.py`, `builders/minjus_ccds.py`).
"""
from __future__ import annotations

from pathlib import Path

from zona4_graph_loader.builders.lugares import build_lugar_layer_rows
from zona4_graph_loader.io.files import DETALLES_PATH, read_json

GEOREF_CATALOG_PATH = Path("data/processed/georef_catalog.json")


def _build(data):
    return build_lugar_layer_rows(
        data,
        use_georef=False,
        georef_catalog_path=GEOREF_CATALOG_PATH,
        georef_min_score=0.76,
        georef_ambiguity_delta=0.02,
    )


def test_direccion_de_domicilio_declara_hecho_narrativo_no_ccd():
    # Ejemplo real de la auditoría (hallazgo I5).
    data = [
        {
            "registro": 1,
            "detalle": {
                "descripcion_lugar_de_secuestro": "Su domicilio, Aráoz 282 5ºA (Capital Federal)",
            },
        }
    ]
    dataset = _build(data)
    direcciones = [l for l in dataset["lugares"] if l.get("tipo_entidad") == "DireccionCCD"]
    assert len(direcciones) == 1
    assert direcciones[0]["tipo_direccion"] == "HECHO_NARRATIVO"
    assert direcciones[0]["tipo_direccion"] != "CCD"


def test_sobre_el_archivo_real_ninguna_direccion_de_esta_fuente_es_ccd():
    data = read_json(DETALLES_PATH)
    dataset = _build(data)
    direcciones = [l for l in dataset["lugares"] if l.get("tipo_entidad") == "DireccionCCD"]
    assert direcciones  # el fix debe estar activo sobre datos reales
    assert all(d["tipo_direccion"] == "HECHO_NARRATIVO" for d in direcciones)
