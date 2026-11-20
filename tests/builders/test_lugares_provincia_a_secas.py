"""Un nombre de provincia a secas en el lugar de secuestro o de asesinato es la
provincia, no su capital homónima.

La fuente escribe la ciudad como "CORDOBA CAPITAL" o "SANTA FE CAPITAL"; el
resolver, en cambio, mandaba "CORDOBA" a secas a la ciudad de Córdoba, mientras
que "TUCUMAN" o "BUENOS AIRES" a secas iban a la provincia. En nacimiento no se
puede decidir y no se toca.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from zona4_graph_loader.builders.lugares import build_lugar_layer_rows

GEOREF_CATALOG_PATH = Path("data/processed/georef_catalog.json")


def _eventos(**detalle):
    rows = build_lugar_layer_rows(
        [{"registro": 1, "detalle": detalle}],
        use_georef=True,
        georef_catalog_path=GEOREF_CATALOG_PATH,
        georef_min_score=0.76,
        georef_ambiguity_delta=0.02,
    )
    return {e["tipo_relacion"]: e["lugar_key"] for e in rows["eventos_espaciales"]}


@pytest.mark.parametrize("texto, provincia", [
    ("CORDOBA", "cordoba"),
    ("Córdoba", "cordoba"),
    ("SAN JUAN", "san_juan"),
    ("Santa Fé", "santa_fe"),
    ("MENDOZA", "mendoza"),
    ("Santiago del Estero", "santiago_del_estero"),
    ("LA RIOJA", "la_rioja"),
])
def test_provincia_a_secas_en_secuestro_y_asesinato_es_la_provincia(texto, provincia):
    eventos = _eventos(descripcion_lugar_de_secuestro=texto, **{"Lugar de asesinato": texto})
    esperado = f"lugar:PROVINCIA:{provincia}|lugar:PAIS:argentina"
    assert eventos["SECUESTRADO_EN"] == esperado
    assert eventos["ASESINADO_EN"] == esperado


def test_en_nacimiento_no_se_toca():
    eventos = _eventos(**{"Lugar de nacimiento": "CORDOBA"})
    assert eventos["NACIO_EN"].startswith("lugar:CIUDAD:cordoba|")


@pytest.mark.parametrize("texto, ciudad", [
    ("CORDOBA CAPITAL", "lugar:CIUDAD:cordoba|"),
    ("SANTA FE CAPITAL", "lugar:CIUDAD:santa_fe|"),
    ("ROSARIO. SANTA FE", "lugar:CIUDAD:rosario|"),
    ("LA PLATA. BS. AS.", "lugar:CIUDAD:la_plata|"),
])
def test_la_ciudad_nombrada_sigue_siendo_la_ciudad(texto, ciudad):
    assert _eventos(descripcion_lugar_de_secuestro=texto)["SECUESTRADO_EN"].startswith(ciudad)


def test_provincias_que_ya_iban_a_la_provincia_no_cambian():
    assert _eventos(descripcion_lugar_de_secuestro="TUCUMAN")["SECUESTRADO_EN"] == (
        "lugar:PROVINCIA:tucuman|lugar:PAIS:argentina"
    )
