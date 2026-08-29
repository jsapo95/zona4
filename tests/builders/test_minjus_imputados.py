from __future__ import annotations

from zona4_graph_loader.builders.minjus_imputados import (
    build_minjus_imputados_rows,
    slug_persona_minjus,
)
from zona4_graph_loader.builders.minjus_sentencias import build_sentencias_index
from zona4_graph_loader.io.raw_files import read_raw_json

IMPUTADO = {
    "source_url": "https://derechoshumanos.mjus.gba.gob.ar/imputado/1-abelleira-hector-jorge",
    "nombre": "Abelleira, Héctor Jorge",
    "datos_personales": {
        "fecha_de_nacimiento": "26/04/1940",
        "fallecido": "No",
        "fuerza": "Policia Provincial",
        "apodo": "El Flaco",
    },
    "sentencias_y_victimas": [
        {
            "sentencia_nombre": "Quinto Cuerpo del Ejército – Bayón",
            "sentencia_url": "/sentencia/1-quinto-cuerpo-del-ejercito-bayon",
            "victimas_asociadas": [
                {
                    "victima_nombre": "Rossi Dario José",
                    "victima_url": "/victima/1870-rossi-dario-jose",
                    "delitos": ["Tormentos", "Homicidio"],
                },
                {"victima_nombre": "meilan Guadalupe", "victima_url": "", "delitos": ["abandono"]},
            ],
        }
    ],
    "condenas_recibidas": [],
}

INDEX = {
    "1-quinto-cuerpo-del-ejercito-bayon": {
        "titulo": "Quinto Cuerpo del Ejército – Bayón",
        "tribunal": "TOF BAHIA BLANCA",
        "fecha": "2012-05-10",
        "origen": "minjus_sentencias:1-quinto-cuerpo-del-ejercito-bayon",
    }
}


def test_slug_persona():
    assert slug_persona_minjus("/imputado/1-abelleira-hector-jorge", "imputado") == "1-abelleira-hector-jorge"
    assert slug_persona_minjus("/victima/1870-rossi-dario-jose", "victima") == "1870-rossi-dario-jose"
    assert slug_persona_minjus("", "victima") is None


def test_imputado_es_represor():
    persona = build_minjus_imputados_rows([IMPUTADO], sentencias_index=INDEX)["personas"][0]
    assert persona["persona_key"] == "minjus_imputado:1-abelleira-hector-jorge"
    assert persona["roles"] == ["REPRESOR"]
    assert persona["fecha_nacimiento"] == "1940-04-26"
    assert persona["fuente"] == "minjus_imputados"


def test_apodo_genera_alias_persona_con_arista_identifica_a():
    dataset = build_minjus_imputados_rows([IMPUTADO], sentencias_index=INDEX)
    alias = [e for e in dataset["entidades_contexto"] if e["tipo_entidad"] == "AliasPersona"]
    assert len(alias) == 1
    assert alias[0]["alias"] == "El Flaco"
    rel = [r for r in dataset["relaciones_contexto"] if r["tipo_relacion"] == "IDENTIFICA_A"]
    assert len(rel) == 1
    assert rel[0]["persona_key"] == "minjus_imputado:1-abelleira-hector-jorge"
    assert rel[0]["entidad_key"] == alias[0]["entidad_key"]


def test_torturo_a_usa_metadatos_de_la_sentencia():
    dataset = build_minjus_imputados_rows([IMPUTADO], sentencias_index=INDEX)
    aristas = [r for r in dataset["relaciones_interpersonales"] if r["tipo"] == "TORTURO_A"]
    assert len(aristas) == 1  # la víctima sin URL no genera arista
    arista = aristas[0]
    assert arista["source_key"] == "minjus_imputado:1-abelleira-hector-jorge"
    assert arista["target_key"] == "minjus_victima:1870-rossi-dario-jose"
    assert arista["fecha"] == "2012-05-10"
    assert arista["fuente"] == "minjus_sentencias:1-quinto-cuerpo-del-ejercito-bayon"


def test_victima_sin_url_no_genera_arista():
    dataset = build_minjus_imputados_rows([IMPUTADO], sentencias_index=INDEX)
    targets = {r["target_key"] for r in dataset["relaciones_interpersonales"]}
    assert not any("meilan" in t for t in targets)


def test_sentencia_fuera_del_index_usa_origen_generico():
    """Slug real (`1-quinto-cuerpo-del-ejercito-bayon`) pero índice vacío: el
    origen se deriva del slug de la sentencia (`minjus_sentencias:{slug}`), no
    de un literal por-builder. Así, si el mismo hecho también aparece en la
    víctima (builder minjus_victimas) sobre un índice vacío, ambos coinciden
    en `fuente` por construcción en lugar de por coincidencia.
    """
    imputado = dict(IMPUTADO)
    dataset = build_minjus_imputados_rows([imputado], sentencias_index={})
    arista = dataset["relaciones_interpersonales"][0]
    assert arista["fuente"] == "minjus_sentencias:1-quinto-cuerpo-del-ejercito-bayon"
    assert arista["fecha"] == "DESCONOCIDA"


def test_sobre_el_archivo_real():
    index = build_sentencias_index(read_raw_json("derechos_humanos_minjus_gba_sentencias.json"))
    dataset = build_minjus_imputados_rows(
        read_raw_json("derechos_humanos_minjus_gba_imputados.json"),
        sentencias_index=index,
    )
    assert len(dataset["personas"]) == 454
    assert all(p["roles"] == ["REPRESOR"] for p in dataset["personas"])
    orgs = [e for e in dataset["entidades_contexto"] if e["tipo_entidad"] == "Org"]
    assert len(orgs) > 5
