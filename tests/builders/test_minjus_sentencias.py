from __future__ import annotations

from zona4_graph_loader.builders.minjus_sentencias import (
    build_sentencias_index,
    slug_sentencia,
)
from zona4_graph_loader.io.raw_files import read_raw_json

SENTENCIA = {
    "post_id": "12562",
    "url_detalle": "https://derechoshumanos.mjus.gba.gob.ar/sentencia/31-abo-atletico-banco-olimpo",
    "titulo": "ABO (Atletico – Banco – Olimpo)",
    "datos_tecnicos": {
        "fecha": "21/12/2010",
        "tribunal": "TOF 2 CAPITAL FEDERAL",
    },
}


def test_slug_normaliza_las_tres_formas_de_url():
    esperado = "31-abo-atletico-banco-olimpo"
    assert slug_sentencia("/sentencia/31-abo-atletico-banco-olimpo") == esperado
    assert slug_sentencia("https://x.gob.ar/sentencia/31-abo-atletico-banco-olimpo") == esperado
    assert slug_sentencia("31-abo-atletico-banco-olimpo") == esperado


def test_slug_de_url_vacia_es_none():
    assert slug_sentencia("") is None
    assert slug_sentencia(None) is None


def test_index_expone_tribunal_y_fecha_iso():
    index = build_sentencias_index([SENTENCIA])
    entrada = index["31-abo-atletico-banco-olimpo"]
    assert entrada["titulo"] == "ABO (Atletico – Banco – Olimpo)"
    assert entrada["tribunal"] == "TOF 2 CAPITAL FEDERAL"
    assert entrada["fecha_sentencia"] == "2010-12-21"
    assert entrada["origen"] == "minjus_sentencias:31-abo-atletico-banco-olimpo"


def test_sentencia_sin_fecha_queda_en_none():
    sentencia = dict(SENTENCIA, datos_tecnicos={"tribunal": "TOF 1"})
    index = build_sentencias_index([sentencia])
    assert index["31-abo-atletico-banco-olimpo"]["fecha_sentencia"] is None


def test_sobre_el_archivo_real():
    # El archivo trae 113 registros, pero dos de ellos (post_id 12514 y 32087)
    # son la misma sentencia "La Cacha" (mismo tribunal, misma fecha, mismo
    # título) publicada dos veces bajo un post_id distinto — sólo cambia la
    # URL en un `/` final y los metadatos de publicación web. Colapsan al
    # mismo slug, dando 112 sentencias distintas en el índice.
    raw = read_raw_json("derechos_humanos_minjus_gba_sentencias.json")
    assert len(raw) == 113
    index = build_sentencias_index(raw)
    assert len(index) == 112
    assert all(entrada["origen"].startswith("minjus_sentencias:") for entrada in index.values())
