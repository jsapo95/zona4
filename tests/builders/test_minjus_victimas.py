from __future__ import annotations

from zona4_graph_loader.builders.minjus_imputados import build_minjus_imputados_rows
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


def test_fecha_secuestro_imposible_no_se_persiste_ni_se_propaga_a_presente_en():
    """Fix E (auditoría 2026-08-29, hallazgo I6). Caso real: Cuatrocchio,
    Daniel Ernesto -- la fuente trae "26/05/2077". No se corrige el valor,
    y esa misma fecha (antes de este fix) se propagaba a PRESENTE_EN.
    """
    cuatrocchio = dict(
        VICTIMA,
        nombre="Cuatrocchio, Daniel Ernesto",
        datos_personales={**VICTIMA["datos_personales"], "fecha_de_secuestro": "26/05/2077"},
    )
    dataset = build_minjus_victimas_rows(
        [cuatrocchio], ccd_key_by_slug=CCD_KEYS, sentencias_index={}
    )
    persona = dataset["personas"][0]
    assert persona["fecha_secuestro"] is None
    presente_en = [e for e in dataset["eventos_espaciales"] if e["tipo_relacion"] == "PRESENTE_EN"]
    assert presente_en[0]["fecha"] == "DESCONOCIDA"


def test_ccd_desconocido_no_genera_evento_huerfano():
    dataset = build_minjus_victimas_rows(
        [VICTIMA], ccd_key_by_slug={}, sentencias_index={}
    )
    assert dataset["eventos_espaciales"] == []


def test_militancia_trabajo_estudios_y_apodo_generan_contexto():
    """`dónde_estudió` son instituciones (facultades, colegios, universidades),
    no oficios: se modelan como `:Institucion`/ESTUDIO_EN, igual que
    `lugar_de_trabajo` (`:Institucion`/TRABAJO_EN). No hay `:Profesion` en este
    builder.
    """
    dataset = build_minjus_victimas_rows(
        [VICTIMA], ccd_key_by_slug=CCD_KEYS, sentencias_index={}
    )
    tipos = {e["tipo_entidad"] for e in dataset["entidades_contexto"]}
    assert tipos == {"Org", "Institucion", "AliasPersona"}

    relaciones = {r["tipo_relacion"] for r in dataset["relaciones_contexto"]}
    assert relaciones == {"PARTE_DE", "TRABAJO_EN", "ESTUDIO_EN", "IDENTIFICA_A"}


def test_trabajo_y_estudio_sentinel_no_generan_institucion():
    """Fix E (auditoría 2026-08-29, hallazgo I3d): "NO DETERMINADO" y
    "NO ESPECIFICADO" no nombran una institución -son la ausencia del dato.
    """
    victima = dict(
        VICTIMA,
        datos_personales={
            **VICTIMA["datos_personales"],
            "lugar_de_trabajo": "No determinado",
            "dónde_estudió": "No especificado",
        },
    )
    dataset = build_minjus_victimas_rows(
        [victima], ccd_key_by_slug=CCD_KEYS, sentencias_index={}
    )
    tipos_relacion = {r["tipo_relacion"] for r in dataset["relaciones_contexto"]}
    assert "TRABAJO_EN" not in tipos_relacion
    assert "ESTUDIO_EN" not in tipos_relacion
    instituciones = [e for e in dataset["entidades_contexto"] if e["tipo_entidad"] == "Institucion"]
    assert instituciones == []


def test_placeholder_de_minjus_no_genera_entidad_ni_relacion():
    """MinJus usa el guión largo "–" como placeholder de "sin dato" en varios
    campos de `datos_personales`. `clean_text` no lo filtra (no está en su
    conjunto de centinelas, que es compartido por todos los builders), y
    `slugify_name("–")` da la cadena vacía. Sin un guardia, cada víctima con
    este placeholder termina compartiendo una `:Org`/`:Institucion` vacía y
    falsa con todas las demás víctimas que también lo tienen sin dato real.
    """
    victima_sin_datos = dict(
        VICTIMA,
        source_url="https://derechoshumanos.mjus.gba.gob.ar/victima/999-sin-datos",
        nombre="Sin Datos, Alguien",
        datos_personales={
            "apodo": "–",
            "militancia": "–",
            "dónde_estudió": "–",
            "lugar_de_trabajo": "–",
            "fecha_de_secuestro": "–",
            "lugar_de_secuestro": "–",
            "situación_actual": "–",
        },
    )
    dataset = build_minjus_victimas_rows(
        [victima_sin_datos], ccd_key_by_slug=CCD_KEYS, sentencias_index={}
    )
    assert dataset["entidades_contexto"] == []
    assert dataset["relaciones_contexto"] == []


def test_par_sin_delito_de_tormentos_da_imputado_por():
    """Espejo de la misma prueba en test_minjus_imputados.py: ejemplo real de
    la auditoría (C1), Cabandié imputado por sustracción de menor, no por
    tormentos."""
    victima = dict(
        VICTIMA,
        source_url="https://derechoshumanos.mjus.gba.gob.ar/victima/3031-cabandie-juan",
        nombre="Cabandié Juan",
        sentencias=[
            {
                "sentencia_nombre": "Plan Sistematico de apropiacion de menores II",
                "sentencia_url": "/sentencia/29-plan-sistematico",
                "imputados": [
                    {
                        "imputado_nombre": "Acosta, Jorge Eduardo",
                        "imputado_url": "/imputado/2-acosta-jorge-eduardo",
                        "delitos": ["Sustracción de menor"],
                    }
                ],
            }
        ],
    )
    dataset = build_minjus_victimas_rows(
        [victima], ccd_key_by_slug=CCD_KEYS, sentencias_index={}
    )
    aristas = dataset["relaciones_interpersonales"]
    assert len(aristas) == 1
    assert aristas[0]["tipo"] == "IMPUTADO_POR"
    assert aristas[0]["delitos"] == ["Sustracción de menor"]


def test_torturo_a_usa_metadatos_de_la_sentencia():
    """Espejo de la misma prueba en test_minjus_imputados.py: la fuente no
    registra cuándo ocurrió la tortura (el hecho), así que `fecha` debe
    quedar en DESCONOCIDA sin importar la sentencia. La fecha del fallo
    (procedencia, no el hecho) se conserva aparte en `fecha_sentencia`
    (Fix 9).
    """
    index = {
        "1-quinto-cuerpo-del-ejercito-bayon": {
            "titulo": "Quinto Cuerpo del Ejército – Bayón",
            "tribunal": "TOF BAHIA BLANCA",
            "fecha_sentencia": "2012-05-10",
            "origen": "minjus_sentencias:1-quinto-cuerpo-del-ejercito-bayon",
        }
    }
    victima = dict(VICTIMA, sentencias=[
        {
            "sentencia_nombre": "Quinto Cuerpo del Ejército – Bayón",
            "sentencia_url": "/sentencia/1-quinto-cuerpo-del-ejercito-bayon",
            "imputados": [
                {
                    "imputado_nombre": "Abelleira, Héctor Jorge",
                    "imputado_url": "/imputado/1-abelleira-hector-jorge",
                    "delitos": ["Tormentos"],
                }
            ],
        }
    ])
    dataset = build_minjus_victimas_rows(
        [victima], ccd_key_by_slug=CCD_KEYS, sentencias_index=index
    )
    arista = dataset["relaciones_interpersonales"][0]
    assert arista["fecha"] == "DESCONOCIDA"
    assert arista["fecha_sentencia"] == "2012-05-10"
    assert arista["fuente"] == "minjus_sentencias:1-quinto-cuerpo-del-ejercito-bayon"
    assert arista["tipo"] == "TORTURO_A"
    assert arista["delitos"] == ["Tormentos"]


def test_registro_sin_url_se_descarta():
    dataset = build_minjus_victimas_rows(
        [dict(VICTIMA, source_url="")], ccd_key_by_slug=CCD_KEYS, sentencias_index={}
    )
    assert dataset["personas"] == []


def test_sentencia_fuera_del_index_usa_origen_generico():
    """Espejo de la misma prueba en test_minjus_imputados.py: slug real de
    sentencia pero índice vacío. El origen se deriva del slug
    (`minjus_sentencias:{slug}`), no de un literal por-builder.
    """
    victima = dict(VICTIMA, sentencias=[
        {
            "sentencia_nombre": "Quinto Cuerpo del Ejército – Bayón",
            "sentencia_url": "/sentencia/1-quinto-cuerpo-del-ejercito-bayon",
            "imputados": [
                {
                    "imputado_nombre": "Abelleira, Héctor Jorge",
                    "imputado_url": "/imputado/1-abelleira-hector-jorge",
                    "delitos": ["Tormentos"],
                }
            ],
        }
    ])
    dataset = build_minjus_victimas_rows(
        [victima], ccd_key_by_slug=CCD_KEYS, sentencias_index={}
    )
    arista = dataset["relaciones_interpersonales"][0]
    assert arista["fuente"] == "minjus_sentencias:1-quinto-cuerpo-del-ejercito-bayon"
    assert arista["fecha"] == "DESCONOCIDA"
    assert arista["fecha_sentencia"] == "DESCONOCIDA"


def test_ambos_builders_acuerdan_fuente_con_indice_vacio():
    """Guarda de regresión central: alimentando el mismo hecho compartido
    (mismo represor, misma víctima, misma sentencia) a ambos builders con un
    índice de sentencias vacío, ambas aristas TORTURO_A deben coincidir en
    `fuente`. Antes de este fix, cada builder caía en su propio literal
    (`minjus_imputados` vs `minjus_victimas`), duplicando cada hecho
    compartido en dos aristas distintas apenas el índice dejara de resolver.
    """
    sentencia_url = "/sentencia/1-quinto-cuerpo-del-ejercito-bayon"
    imputado = {
        "source_url": "https://derechoshumanos.mjus.gba.gob.ar/imputado/1-abelleira-hector-jorge",
        "nombre": "Abelleira, Héctor Jorge",
        "datos_personales": {},
        "sentencias_y_victimas": [
            {
                "sentencia_nombre": "Quinto Cuerpo del Ejército – Bayón",
                "sentencia_url": sentencia_url,
                "victimas_asociadas": [
                    {
                        "victima_nombre": "Abachian, Juan Carlos",
                        "victima_url": "/victima/213-abachian-juan-carlos",
                        "delitos": ["Tormentos"],
                    }
                ],
            }
        ],
    }
    victima = dict(VICTIMA, sentencias=[
        {
            "sentencia_nombre": "Quinto Cuerpo del Ejército – Bayón",
            "sentencia_url": sentencia_url,
            "imputados": [
                {
                    "imputado_nombre": "Abelleira, Héctor Jorge",
                    "imputado_url": "/imputado/1-abelleira-hector-jorge",
                    "delitos": ["Tormentos"],
                }
            ],
        }
    ])

    dataset_imputados = build_minjus_imputados_rows([imputado], sentencias_index={})
    dataset_victimas = build_minjus_victimas_rows(
        [victima], ccd_key_by_slug=CCD_KEYS, sentencias_index={}
    )

    fuente_imputados = dataset_imputados["relaciones_interpersonales"][0]["fuente"]
    fuente_victimas = dataset_victimas["relaciones_interpersonales"][0]["fuente"]
    assert fuente_imputados == fuente_victimas


def test_ambos_builders_acuerdan_tipo_y_delitos_para_un_par_sin_tormentos():
    """Fix C1: la clasificación TORTURO_A/IMPUTADO_POR se calcula con la
    misma función compartida (`clasificar_relacion_por_delitos`) en ambos
    builders. Si un lado clasificara distinto que el otro para el mismo
    hecho, quedarían dos aristas paralelas de tipo distinto para el mismo par
    imputado-víctima -exactamente el riesgo que este test cubre, usando un
    par sin ningún delito de la familia de tormentos.
    """
    sentencia_url = "/sentencia/29-plan-sistematico"
    delitos = ["Sustracción de menor"]
    imputado = {
        "source_url": "https://derechoshumanos.mjus.gba.gob.ar/imputado/2-acosta-jorge-eduardo",
        "nombre": "Acosta, Jorge Eduardo",
        "datos_personales": {},
        "sentencias_y_victimas": [
            {
                "sentencia_nombre": "Plan Sistematico de apropiacion de menores II",
                "sentencia_url": sentencia_url,
                "victimas_asociadas": [
                    {
                        "victima_nombre": "Cabandié Juan",
                        "victima_url": "/victima/3031-cabandie-juan",
                        "delitos": delitos,
                    }
                ],
            }
        ],
    }
    victima = dict(
        VICTIMA,
        source_url="https://derechoshumanos.mjus.gba.gob.ar/victima/3031-cabandie-juan",
        nombre="Cabandié Juan",
        sentencias=[
            {
                "sentencia_nombre": "Plan Sistematico de apropiacion de menores II",
                "sentencia_url": sentencia_url,
                "imputados": [
                    {
                        "imputado_nombre": "Acosta, Jorge Eduardo",
                        "imputado_url": "/imputado/2-acosta-jorge-eduardo",
                        "delitos": delitos,
                    }
                ],
            }
        ],
    )

    dataset_imputados = build_minjus_imputados_rows([imputado], sentencias_index={})
    dataset_victimas = build_minjus_victimas_rows(
        [victima], ccd_key_by_slug=CCD_KEYS, sentencias_index={}
    )

    arista_imputados = dataset_imputados["relaciones_interpersonales"][0]
    arista_victimas = dataset_victimas["relaciones_interpersonales"][0]
    assert arista_imputados["tipo"] == arista_victimas["tipo"] == "IMPUTADO_POR"
    assert arista_imputados["delitos"] == arista_victimas["delitos"] == delitos


def test_sobre_el_archivo_real():
    index = build_sentencias_index(read_raw_json("derechos_humanos_minjus_gba_sentencias.json"))
    dataset = build_minjus_victimas_rows(
        read_raw_json("derechos_humanos_minjus_gba_victimas.json"),
        ccd_key_by_slug={},
        sentencias_index=index,
    )
    assert len(dataset["personas"]) == 3257

    # Fix E (hallazgo I6): los 12 registros con fecha_secuestro imposible que
    # encontró la auditoría (1997, 2023, 2024, 2077) no deben quedar
    # persistidos; el resto (min real 1974) no debe verse afectado.
    con_fecha = [p for p in dataset["personas"] if p.get("fecha_secuestro")]
    assert all(1966 <= int(p["fecha_secuestro"][:4]) <= 1990 for p in con_fecha)
    assert min(int(p["fecha_secuestro"][:4]) for p in con_fecha) == 1974
    cuatrocchio = next(p for p in dataset["personas"] if p["nombre"] == "Cuatrocchio, Daniel Ernesto")
    assert cuatrocchio["fecha_secuestro"] is None
    con_fecha = [p for p in dataset["personas"] if p["fecha_secuestro"]]
    assert len(con_fecha) > 2900
    assert dataset["eventos_espaciales"] == []  # sin ccd_key_by_slug no hay lugares

    # Fix E (hallazgo I3d): ninguna :Institución generada por esta fuente
    # debe tener un nombre sentinel puro.
    from zona4_graph_loader.constants import SENTINEL_INSTITUCION_VALUES

    instituciones = [e for e in dataset["entidades_contexto"] if e["tipo_entidad"] == "Institucion"]
    assert all(inst["nombre"] not in SENTINEL_INSTITUCION_VALUES for inst in instituciones)
