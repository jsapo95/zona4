"""Regresión: Fix E (hallazgo I6 de la auditoría semántica 2026-08-29).

`build_lugar_layer_rows` parseaba `descripcion_fecha_nacimiento`,
`descripcion_fecha_de_secuestro` y `descripcion_fecha_de_asesinato` con
`parse_ddmmyyyy` sin ninguna validación de plausibilidad. La fuente trae
erratas de tipeo que producen fechas imposibles (nacimientos en 2021-2052;
la auditoría documenta 7 casos reales), y esas fechas pasaban intactas a las
aristas `NACIO_EN`/`SECUESTRADO_EN`/`ASESINADO_EN`.
"""
from __future__ import annotations

from pathlib import Path

from zona4_graph_loader.builders.lugares import build_lugar_layer_rows
from zona4_graph_loader.io.files import DETALLES_PATH, read_json

GEOREF_CATALOG_PATH = Path("data/processed/georef_catalog.json")


def _registro(registro, **detalle_overrides):
    detalle = {
        "descripcion_lugar_de_secuestro": "La Plata. BS. AS.",
        "Lugar de nacimiento": "La Plata. BS. AS.",
        "Lugar de asesinato": "La Plata. BS. AS.",
    }
    detalle.update(detalle_overrides)
    return {"registro": registro, "detalle": detalle}


def _build(data):
    return build_lugar_layer_rows(
        data,
        use_georef=False,
        georef_catalog_path=GEOREF_CATALOG_PATH,
        georef_min_score=0.76,
        georef_ambiguity_delta=0.02,
    )


def _fecha_por_tipo(eventos, tipo):
    return [e["fecha"] for e in eventos if e["tipo_relacion"] == tipo]


def test_nacimiento_futuro_imposible_queda_desconocida():
    # Caso real de la auditoría: Valcarce, Alfredo -- fuente "23/12/2052".
    data = [_registro(1, **{"descripcion_fecha_nacimiento": "23/12/2052"})]
    dataset = _build(data)
    fechas = _fecha_por_tipo(dataset["eventos_espaciales"], "NACIO_EN")
    assert fechas == ["DESCONOCIDA"]


def test_nacimiento_dentro_de_rango_se_conserva():
    data = [_registro(1, **{"descripcion_fecha_nacimiento": "13/12/1951"})]
    dataset = _build(data)
    fechas = _fecha_por_tipo(dataset["eventos_espaciales"], "NACIO_EN")
    assert fechas == ["1951-12-13"]


def test_secuestro_fuera_de_rango_queda_desconocida():
    # Caso real de la auditoría (vía minjus_victimas, pero mismo guardia
    # aplicado acá a Parque de la Memoria): un secuestro en 1997 o 2077 es
    # imposible para esta fuente.
    data = [_registro(1, **{"descripcion_fecha_de_secuestro": "26/05/2077"})]
    dataset = _build(data)
    fechas = _fecha_por_tipo(dataset["eventos_espaciales"], "SECUESTRADO_EN")
    assert fechas == ["DESCONOCIDA"]


def test_asesinato_fuera_de_rango_queda_desconocida():
    data = [_registro(1, **{"descripcion_fecha_de_asesinato": "07/09/1950"})]
    dataset = _build(data)
    fechas = _fecha_por_tipo(dataset["eventos_espaciales"], "ASESINADO_EN")
    assert fechas == ["DESCONOCIDA"]


def test_asesinato_dentro_de_rango_se_conserva():
    data = [_registro(1, **{"descripcion_fecha_de_asesinato": "15/05/1976"})]
    dataset = _build(data)
    fechas = _fecha_por_tipo(dataset["eventos_espaciales"], "ASESINADO_EN")
    assert fechas == ["1976-05-15"]


def test_sobre_el_archivo_real_ninguna_fecha_nacimiento_supera_1983():
    data = read_json(DETALLES_PATH)
    dataset = _build(data)
    fechas_nacio_en = _fecha_por_tipo(dataset["eventos_espaciales"], "NACIO_EN")
    anios_imposibles = [f for f in fechas_nacio_en if f != "DESCONOCIDA" and int(f[:4]) > 1983]
    assert anios_imposibles == []

    fechas_secuestro = _fecha_por_tipo(dataset["eventos_espaciales"], "SECUESTRADO_EN")
    fuera_de_rango = [f for f in fechas_secuestro if f != "DESCONOCIDA" and not (1966 <= int(f[:4]) <= 1990)]
    assert fuera_de_rango == []

    fechas_asesinato = _fecha_por_tipo(dataset["eventos_espaciales"], "ASESINADO_EN")
    fuera_de_rango_ase = [f for f in fechas_asesinato if f != "DESCONOCIDA" and not (1966 <= int(f[:4]) <= 1990)]
    assert fuera_de_rango_ase == []

    # Los 7 nacimientos imposibles reales de la auditoría (2021-2052) deben
    # quedar en DESCONOCIDA, no perderse silenciosamente ni desaparecer el
    # evento: el lugar (La Plata en algunos casos) puede seguir resolviendo,
    # sólo la fecha se descarta.
    desconocidas = sum(1 for f in fechas_nacio_en if f == "DESCONOCIDA")
    assert desconocidas >= 7
