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
        "fecha_sentencia": "2012-05-10",
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


def test_fecha_nacimiento_imposible_no_se_persiste():
    """Fix E (auditoría 2026-08-29, hallazgo I6). Caso real:
    Massera, Emilio Eduardo -- la fuente trae "08/11/2010" (probablemente
    confundida con su fecha real de fallecimiento, también 2010); nació en
    1925. No se corrige el valor -se descarta.
    """
    massera = dict(
        IMPUTADO,
        nombre="Massera, Emilio Eduardo",
        datos_personales={**IMPUTADO["datos_personales"], "fecha_de_nacimiento": "08/11/2010"},
    )
    persona = build_minjus_imputados_rows([massera], sentencias_index=INDEX)["personas"][0]
    assert persona["fecha_nacimiento"] is None


def test_sobre_el_archivo_real_massera_no_tiene_fecha_de_nacimiento_imposible():
    data = read_raw_json("derechos_humanos_minjus_gba_imputados.json")
    dataset = build_minjus_imputados_rows(data, sentencias_index={})
    massera = next(p for p in dataset["personas"] if p["nombre"] == "Massera, Emilio Eduardo")
    assert massera["fecha_nacimiento"] is None

    # Ninguna fecha_nacimiento de esta fuente debería superar 1983 (fin de
    # la dictadura); el máximo real verificado es 1979.
    con_fecha = [p for p in dataset["personas"] if p.get("fecha_nacimiento")]
    assert all(int(p["fecha_nacimiento"][:4]) <= 1983 for p in con_fecha)


def test_apodo_genera_alias_persona_con_arista_identifica_a():
    dataset = build_minjus_imputados_rows([IMPUTADO], sentencias_index=INDEX)
    alias = [e for e in dataset["entidades_contexto"] if e["tipo_entidad"] == "AliasPersona"]
    assert len(alias) == 1
    assert alias[0]["alias"] == "El Flaco"
    rel = [r for r in dataset["relaciones_contexto"] if r["tipo_relacion"] == "IDENTIFICA_A"]
    assert len(rel) == 1
    assert rel[0]["persona_key"] == "minjus_imputado:1-abelleira-hector-jorge"
    assert rel[0]["entidad_key"] == alias[0]["entidad_key"]


def test_torturo_a_lleva_delitos_y_solo_para_el_par_con_tormentos():
    """Fix C1: el par Rossi/Abelleira tiene 'Tormentos' entre sus delitos
    (TORTURO_A); si además hubiera un par sin tormentos, ese debería recibir
    IMPUTADO_POR en su lugar (cubierto abajo con un imputado dedicado)."""
    dataset = build_minjus_imputados_rows([IMPUTADO], sentencias_index=INDEX)
    aristas = dataset["relaciones_interpersonales"]
    assert len(aristas) == 1
    arista = aristas[0]
    assert arista["tipo"] == "TORTURO_A"
    assert arista["delitos"] == ["Tormentos", "Homicidio"]


def test_par_sin_delito_de_tormentos_da_imputado_por():
    """Ejemplo real de la auditoría (C1): Acosta imputado por sustracción de
    menor contra Juan Cabandié, no por tormentos. El grafo no debe afirmar
    tortura para un par que la sentencia condena por otro delito."""
    imputado = {
        "source_url": "https://derechoshumanos.mjus.gba.gob.ar/imputado/2-acosta-jorge-eduardo",
        "nombre": "Acosta, Jorge Eduardo",
        "datos_personales": {},
        "sentencias_y_victimas": [
            {
                "sentencia_nombre": "Plan Sistematico de apropiacion de menores II",
                "sentencia_url": "/sentencia/29-plan-sistematico",
                "victimas_asociadas": [
                    {
                        "victima_nombre": "Cabandié Juan",
                        "victima_url": "/victima/3031-cabandie-juan",
                        "delitos": ["Sustracción de menor"],
                    }
                ],
            }
        ],
    }
    dataset = build_minjus_imputados_rows([imputado], sentencias_index={})
    aristas = dataset["relaciones_interpersonales"]
    assert len(aristas) == 1
    assert aristas[0]["tipo"] == "IMPUTADO_POR"
    assert aristas[0]["delitos"] == ["Sustracción de menor"]


def test_par_sin_delitos_en_la_fuente_da_imputado_por_con_delitos_vacios():
    imputado = dict(IMPUTADO, sentencias_y_victimas=[
        {
            "sentencia_nombre": "X",
            "sentencia_url": "/sentencia/x",
            "victimas_asociadas": [
                {"victima_nombre": "Sin Delitos", "victima_url": "/victima/1-sin-delitos"},
            ],
        }
    ])
    dataset = build_minjus_imputados_rows([imputado], sentencias_index={})
    arista = dataset["relaciones_interpersonales"][0]
    assert arista["tipo"] == "IMPUTADO_POR"
    assert arista["delitos"] == []


def test_torturo_a_usa_metadatos_de_la_sentencia():
    """La fuente no registra cuándo ocurrió la tortura (el hecho): `fecha`
    debe quedar en DESCONOCIDA sin importar la sentencia. La fecha del fallo
    (procedencia, no el hecho) se conserva aparte, en `fecha_sentencia`
    (Fix 9: antes esta prueba afirmaba que la tortura ocurrió el día del
    fallo, décadas después del hecho real).
    """
    dataset = build_minjus_imputados_rows([IMPUTADO], sentencias_index=INDEX)
    aristas = [r for r in dataset["relaciones_interpersonales"] if r["tipo"] == "TORTURO_A"]
    assert len(aristas) == 1  # la víctima sin URL no genera arista
    arista = aristas[0]
    assert arista["source_key"] == "minjus_imputado:1-abelleira-hector-jorge"
    assert arista["target_key"] == "minjus_victima:1870-rossi-dario-jose"
    assert arista["fecha"] == "DESCONOCIDA"
    assert arista["fecha_sentencia"] == "2012-05-10"
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
    assert arista["fecha_sentencia"] == "DESCONOCIDA"


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


def test_sobre_el_archivo_real_ninguna_torturo_a_sin_delito_de_tormentos():
    """Invariante central del fix C1: sobre el archivo real completo, cada
    arista TORTURO_A debe tener al menos un delito de la familia de
    tormentos entre sus `delitos`, y ninguna arista IMPUTADO_POR debe
    tenerlo (si lo tuviera, debería haber sido clasificada como TORTURO_A).
    """
    index = build_sentencias_index(read_raw_json("derechos_humanos_minjus_gba_sentencias.json"))
    dataset = build_minjus_imputados_rows(
        read_raw_json("derechos_humanos_minjus_gba_imputados.json"),
        sentencias_index=index,
    )
    torturo_a = [r for r in dataset["relaciones_interpersonales"] if r["tipo"] == "TORTURO_A"]
    imputado_por = [r for r in dataset["relaciones_interpersonales"] if r["tipo"] == "IMPUTADO_POR"]
    assert torturo_a and imputado_por  # el archivo real tiene ambos casos
    familia_tormentos = {"tormentos", "tormentos seguidos de muerte"}
    for arista in torturo_a:
        delitos_norm = {d.strip().lower() for d in arista["delitos"]}
        assert delitos_norm & familia_tormentos, arista
    for arista in imputado_por:
        delitos_norm = {d.strip().lower() for d in arista["delitos"]}
        assert not (delitos_norm & familia_tormentos), arista
