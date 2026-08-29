from __future__ import annotations

from zona4_graph_loader.builders.minjus_victimas import build_minjus_victimas_rows
from zona4_graph_loader.builders.minjus_sentencias import build_sentencias_index
from zona4_graph_loader.io.raw_files import read_raw_json

VICTIMA = {
    "source_url": "https://derechoshumanos.mjus.gba.gob.ar/victima/213-abachian-juan-carlos",
    "nombre": "Abachian, Juan Carlos",
    "datos_personales": {
        "apodo": "El Armenio",
        "militancia": "Juventud Peronista",
        "dónde_estudió": "Abogacía",
        "lugar_de_trabajo": "Taller de chapa y pintura",
        "fecha_de_secuestro": "20/01/1977",
        "lugar_de_secuestro": "Calle 7 779",
        "situación_actual": "Persona desaparecida",
    },
    "centros_clandestinos": [
        {"nombre": "COMISARÍA 5ª DE LA PLATA", "url": "/centrodetencion/69-comisaria-5-de-la-plata"},
    ],
    "sentencias": [],
}

CCD_KEYS = {"69-comisaria-5-de-la-plata": "lugar:CCD:69_comisaria_5_de_la_plata"}


def test_victima_basica():
    persona = build_minjus_victimas_rows(
        [VICTIMA], ccd_key_by_slug=CCD_KEYS, sentencias_index={}
    )["personas"][0]
    assert persona["persona_key"] == "minjus_victima:213-abachian-juan-carlos"
    assert persona["roles"] == ["VICTIMA"]
    assert persona["genero"] == "INDETERMINADO"
    assert persona["fecha_secuestro"] == "1977-01-20"


def test_no_genera_secuestrado_en_por_texto_libre():
    """El parsing de lugar_de_secuestro está fuera de alcance en esta ronda."""
    dataset = build_minjus_victimas_rows(
        [VICTIMA], ccd_key_by_slug=CCD_KEYS, sentencias_index={}
    )
    tipos = {e["tipo_relacion"] for e in dataset["eventos_espaciales"]}
    assert "SECUESTRADO_EN" not in tipos


def test_ccd_genera_presente_en():
    dataset = build_minjus_victimas_rows(
        [VICTIMA], ccd_key_by_slug=CCD_KEYS, sentencias_index={}
    )
    eventos = [e for e in dataset["eventos_espaciales"] if e["tipo_relacion"] == "PRESENTE_EN"]
    assert len(eventos) == 1
    assert eventos[0]["lugar_key"] == "lugar:CCD:69_comisaria_5_de_la_plata"
    assert eventos[0]["persona_key"] == "minjus_victima:213-abachian-juan-carlos"
    assert eventos[0]["fecha"] == "1977-01-20"


def test_ccd_desconocido_no_genera_evento_huerfano():
    dataset = build_minjus_victimas_rows(
        [VICTIMA], ccd_key_by_slug={}, sentencias_index={}
    )
    assert dataset["eventos_espaciales"] == []


def test_militancia_trabajo_estudios_y_apodo_generan_contexto():
    dataset = build_minjus_victimas_rows(
        [VICTIMA], ccd_key_by_slug=CCD_KEYS, sentencias_index={}
    )
    tipos = {e["tipo_entidad"] for e in dataset["entidades_contexto"]}
    assert tipos == {"Org", "Institucion", "Profesion", "AliasPersona"}

    relaciones = {r["tipo_relacion"] for r in dataset["relaciones_contexto"]}
    assert relaciones == {"PARTE_DE", "TRABAJO_EN", "EJERCIO", "IDENTIFICA_A"}


def test_registro_sin_url_se_descarta():
    dataset = build_minjus_victimas_rows(
        [dict(VICTIMA, source_url="")], ccd_key_by_slug=CCD_KEYS, sentencias_index={}
    )
    assert dataset["personas"] == []


def test_sobre_el_archivo_real():
    index = build_sentencias_index(read_raw_json("derechos_humanos_minjus_gba_sentencias.json"))
    dataset = build_minjus_victimas_rows(
        read_raw_json("derechos_humanos_minjus_gba_victimas.json"),
        ccd_key_by_slug={},
        sentencias_index=index,
    )
    assert len(dataset["personas"]) == 3257
    con_fecha = [p for p in dataset["personas"] if p["fecha_secuestro"]]
    assert len(con_fecha) > 2900
    assert dataset["eventos_espaciales"] == []  # sin ccd_key_by_slug no hay lugares
