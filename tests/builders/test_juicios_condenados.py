from __future__ import annotations

from zona4_graph_loader.builders.juicios_condenados import build_juicios_condenados_rows
from zona4_graph_loader.io.raw_files import read_raw_json


def _payload(*condenados):
    return {"resultado": {"condenado": [{"condenados": c} for c in condenados]}}


MILITAR = {
    "impu_id": 2691,
    "apellido_nombre": "ABALLAY, Juan Alberto",
    "Categoria": "FUERZAS DE SEGURIDAD",
    "Fuerza": "POLICIA FEDERAL ARGENTINA",
    "Nacimiento": "09-04-1948",
}
CIVIL = {
    "impu_id": 3001,
    "apellido_nombre": "GOMEZ, Pedro",
    "Categoria": "CIVILES",
    "Fuerza": None,
    "Nacimiento": None,
}


def test_militar_es_represor():
    persona = build_juicios_condenados_rows(_payload(MILITAR))["personas"][0]
    assert persona["persona_key"] == "juicios_condenado:2691"
    assert persona["nombre"] == "ABALLAY, Juan Alberto"
    assert persona["roles"] == ["REPRESOR"]
    assert persona["genero"] == "INDETERMINADO"
    assert persona["fuente"] == "juicios_condenados"


def test_civil_es_represor_y_complice_civil():
    persona = build_juicios_condenados_rows(_payload(CIVIL))["personas"][0]
    assert persona["roles"] == ["COMPLICE", "REPRESOR"]
    assert persona["complice_tipo"] == "CIVIL"


def test_nacimiento_ddmmyyyy_con_guiones_se_normaliza_a_iso():
    persona = build_juicios_condenados_rows(_payload(MILITAR))["personas"][0]
    assert persona["fecha_nacimiento"] == "1948-04-09"


def test_nacimiento_ausente_queda_en_none():
    persona = build_juicios_condenados_rows(_payload(CIVIL))["personas"][0]
    assert persona["fecha_nacimiento"] is None


def test_nacimiento_con_fecha_de_fallecimiento_toma_solo_el_nacimiento():
    # El campo Nacimiento del dataset real codifica a veces "nacimiento/fallecimiento"
    # (ej. "01-09-1941/18-04-2015") para condenados fallecidos. Sólo nos interesa
    # el primer componente.
    condenado = dict(MILITAR, Nacimiento="09-04-1948/18-04-2015")
    persona = build_juicios_condenados_rows(_payload(condenado))["personas"][0]
    assert persona["fecha_nacimiento"] == "1948-04-09"


def test_nacimiento_imposible_no_se_persiste():
    # Fix E (auditoría 2026-08-29, hallazgo I6): mismo guardia que en
    # minjus_imputados.py, aplicado por consistencia aunque esta fuente no
    # tenga hoy ningún valor fuera de rango (verificado: 1923-1979).
    condenado = dict(MILITAR, Nacimiento="09-04-2010")
    persona = build_juicios_condenados_rows(_payload(condenado))["personas"][0]
    assert persona["fecha_nacimiento"] is None


def test_fuerza_genera_org_y_relacion_parte_de():
    dataset = build_juicios_condenados_rows(_payload(MILITAR))
    org = dataset["entidades_contexto"][0]
    assert org["tipo_entidad"] == "Org"
    assert org["entidad_key"] == "org:policia_federal_argentina"
    assert org["nombre"] == "POLICIA FEDERAL ARGENTINA"
    rel = dataset["relaciones_contexto"][0]
    assert rel["tipo_relacion"] == "PARTE_DE"
    assert rel["persona_key"] == "juicios_condenado:2691"
    assert rel["entidad_key"] == "org:policia_federal_argentina"
    # Regla 1.2 de auditoría: toda arista lleva fecha y origen.
    assert rel["fecha"] == "DESCONOCIDA"
    assert rel["origen"] == "juicios_condenados"


def test_sin_fuerza_no_genera_org():
    dataset = build_juicios_condenados_rows(_payload(CIVIL))
    assert dataset["entidades_contexto"] == []
    assert dataset["relaciones_contexto"] == []


def test_fuerza_se_persiste_en_la_persona():
    persona = build_juicios_condenados_rows(_payload(MILITAR))["personas"][0]
    assert persona["fuerza"] == "POLICIA FEDERAL ARGENTINA"


def test_fuerza_sentinel_no_genera_org_pero_se_persiste_en_la_persona():
    """Fix E (auditoría 2026-08-29, hallazgo I3d): "SIN ESPECIFICAR" no es
    una organización -materializarlo agrupaba a 109 represores distintos
    (combinando esta fuente con minjus_imputados) bajo una membresía
    compartida falsa. El dato no se pierde: se persiste en
    `Persona.fuerza`.
    """
    condenado = dict(MILITAR, Fuerza="SIN ESPECIFICAR")
    dataset = build_juicios_condenados_rows(_payload(condenado))
    assert dataset["entidades_contexto"] == []
    assert dataset["relaciones_contexto"] == []
    assert dataset["personas"][0]["fuerza"] == "SIN ESPECIFICAR"


def test_fuerza_civil_no_genera_org():
    # "CIVIL" no es una organización: es la ausencia de fuerza represiva.
    condenado = dict(MILITAR, Fuerza="Civil")
    dataset = build_juicios_condenados_rows(_payload(condenado))
    assert dataset["entidades_contexto"] == []
    assert dataset["personas"][0]["fuerza"] == "CIVIL"


def test_registro_sin_impu_id_se_descarta():
    dataset = build_juicios_condenados_rows(_payload(dict(MILITAR, impu_id=None)))
    assert dataset["personas"] == []


def test_sobre_el_archivo_real():
    dataset = build_juicios_condenados_rows(
        read_raw_json("juicios_lesa_humanidad_condenados.json")
    )
    assert len(dataset["personas"]) == 1237
    complices = [p for p in dataset["personas"] if "COMPLICE" in p["roles"]]
    assert len(complices) == 197
    assert all(p["complice_tipo"] == "CIVIL" for p in complices)
    assert len([p for p in dataset["personas"] if p["fecha_nacimiento"]]) == 1232

    # Fix E (hallazgo I3d): ningún :Org generado a partir de esta fuente
    # debe llevar un nombre sentinel.
    from zona4_graph_loader.constants import SENTINEL_ORG_VALUES

    orgs = [e for e in dataset["entidades_contexto"] if e["tipo_entidad"] == "Org"]
    assert all(org["nombre"] not in SENTINEL_ORG_VALUES for org in orgs)

    # 85 represores reales tienen Fuerza:"SIN ESPECIFICAR" y 65 "CIVIL"
    # (verificado sobre el archivo crudo); ninguno debe generar PARTE_DE, y
    # el valor debe seguir presente en Persona.fuerza.
    sin_especificar = [p for p in dataset["personas"] if p.get("fuerza") == "SIN ESPECIFICAR"]
    civiles_fuerza = [p for p in dataset["personas"] if p.get("fuerza") == "CIVIL"]
    assert len(sin_especificar) == 85
    assert len(civiles_fuerza) == 65
    entidad_keys_con_parte_de = {r["entidad_key"] for r in dataset["relaciones_contexto"]}
    assert "org:sin_especificar" not in entidad_keys_con_parte_de
    assert "org:civil" not in entidad_keys_con_parte_de
