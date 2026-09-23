from __future__ import annotations

from zona4_graph_loader.builders.minjus_sentencias import (
    build_sentencias_index,
    clasificar_relacion_por_delitos,
    limpiar_delitos,
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


def test_clasificar_delitos_con_tormentos_da_torturo_a():
    assert clasificar_relacion_por_delitos(["Privación Ilegítima de la libertad", "Tormentos"]) == "TORTURO_A"


def test_clasificar_delitos_con_tormentos_seguidos_de_muerte_da_torturo_a():
    assert clasificar_relacion_por_delitos(["Tormentos seguidos de muerte"]) == "TORTURO_A"


def test_clasificar_delitos_es_insensible_a_mayusculas_y_espacios():
    assert clasificar_relacion_por_delitos(["  TORMENTOS  "]) == "TORTURO_A"
    assert clasificar_relacion_por_delitos(["tormentos"]) == "TORTURO_A"


def test_clasificar_delitos_sin_tormentos_da_imputado_por():
    """Ejemplo real de la auditoría (C1): Acosta/Vañek/Bignone imputados por
    sustracción de menor contra Juan Cabandié, no por tormentos."""
    assert clasificar_relacion_por_delitos(["Sustracción de menor"]) == "IMPUTADO_POR"
    assert clasificar_relacion_por_delitos(["Homicidio", "Privación Ilegítima de la libertad"]) == "IMPUTADO_POR"


def test_clasificar_delitos_vacios_o_ausentes_da_imputado_por():
    assert clasificar_relacion_por_delitos([]) == "IMPUTADO_POR"
    assert clasificar_relacion_por_delitos(None) == "IMPUTADO_POR"


def test_clasificar_apremios_ilegales_no_es_tormentos():
    """Apremios ilegales es un tipo penal propio (art. 144 bis inc. 3), lesser
    included pero legalmente distinto de tormentos (art. 144 ter); la
    auditoría no lo incluye en la familia de tormentos."""
    assert clasificar_relacion_por_delitos(["Apremios ilegales"]) == "IMPUTADO_POR"


def test_limpiar_delitos_preserva_texto_original_y_descarta_vacios():
    assert limpiar_delitos(["Tormentos", "  ", "", "Homicidio"]) == ["Tormentos", "Homicidio"]
    assert limpiar_delitos(None) == []


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
