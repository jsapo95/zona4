from __future__ import annotations

from typing import Any, Dict, List

from zona4_graph_loader.builders.base import CanonicalDataset
from zona4_graph_loader.builders.minjus_ccds import slug_ccd
from zona4_graph_loader.builders.minjus_imputados import slug_persona_minjus
from zona4_graph_loader.builders.minjus_sentencias import slug_sentencia
from zona4_graph_loader.domain.date_norm import parse_ddmmyyyy
from zona4_graph_loader.domain.text_norm import clean_text, slugify_name

FUENTE = "minjus_victimas"


def build_minjus_victimas_rows(
    data: List[Dict[str, Any]],
    *,
    ccd_key_by_slug: Dict[str, str],
    sentencias_index: Dict[str, Dict[str, Any]],
) -> CanonicalDataset:
    """Convierte las víctimas de MinJus GBA al CDM.

    NO genera aristas SECUESTRADO_EN: `lugar_de_secuestro` es texto narrativo y su
    parsing quedó fuera de alcance. La fecha de secuestro se persiste en el nodo
    (`fecha_secuestro`) para no perderla y para alimentar la reconciliación.

    La capa espacial sale de `centros_clandestinos`, que trae URLs resolubles
    contra el mapa que produce el builder de CCDs.
    """
    personas: List[Dict[str, Any]] = []
    eventos: List[Dict[str, Any]] = []
    relaciones: List[Dict[str, Any]] = []
    entidades: Dict[str, Dict[str, Any]] = {}
    rel_contexto: List[Dict[str, Any]] = []

    def registrar_entidad(entidad_key, tipo_entidad, campo, valor, tipo_relacion, persona_key):
        entidades.setdefault(entidad_key, {
            "entidad_key": entidad_key,
            "tipo_entidad": tipo_entidad,
            campo: valor,
            "fuente": FUENTE,
        })
        rel_contexto.append({
            "persona_key": persona_key,
            "entidad_key": entidad_key,
            "tipo_relacion": tipo_relacion,
            "fecha": "DESCONOCIDA",
            "origen": FUENTE,
        })

    for item in data:
        slug = slug_persona_minjus(item.get("source_url"), "victima")
        nombre = clean_text(item.get("nombre"))
        if not slug or not nombre:
            continue

        persona_key = f"minjus_victima:{slug}"
        datos = item.get("datos_personales") or {}
        fecha_secuestro = parse_ddmmyyyy(clean_text(datos.get("fecha_de_secuestro")))

        personas.append({
            "persona_key": persona_key,
            "nombre": nombre,
            "genero": "INDETERMINADO",
            "fuente": FUENTE,
            "roles": ["VICTIMA"],
            "fecha_secuestro": fecha_secuestro,
        })

        militancia = clean_text(datos.get("militancia"))
        if militancia:
            registrar_entidad(
                f"org:{slugify_name(militancia.upper())}", "Org", "nombre",
                militancia.upper(), "PARTE_DE", persona_key,
            )

        trabajo = clean_text(datos.get("lugar_de_trabajo"))
        if trabajo:
            registrar_entidad(
                f"institucion:{slugify_name(trabajo.upper())}", "Institucion", "nombre",
                trabajo.upper(), "TRABAJO_EN", persona_key,
            )

        estudios = clean_text(datos.get("dónde_estudió"))
        if estudios:
            registrar_entidad(
                f"profesion:{slugify_name(estudios.upper())}", "Profesion", "descripcion",
                estudios.upper(), "EJERCIO", persona_key,
            )

        apodo = clean_text(datos.get("apodo"))
        if apodo:
            registrar_entidad(
                f"alias_persona:{slugify_name(apodo)}|{slug}", "AliasPersona", "alias",
                apodo, "IDENTIFICA_A", persona_key,
            )

        for ccd in item.get("centros_clandestinos") or []:
            slug_centro = slug_ccd(ccd.get("url"))
            lugar_key = ccd_key_by_slug.get(slug_centro or "")
            if not lugar_key:
                continue
            eventos.append({
                "persona_key": persona_key,
                "lugar_key": lugar_key,
                "tipo_relacion": "PRESENTE_EN",
                "fecha": fecha_secuestro or "DESCONOCIDA",
                "origen": FUENTE,
            })

        for sentencia in item.get("sentencias") or []:
            slug_sent = slug_sentencia(sentencia.get("sentencia_url"))
            meta = sentencias_index.get(slug_sent or "", {})
            origen = meta.get("origen") or FUENTE
            fecha = meta.get("fecha") or "DESCONOCIDA"

            for imputado in sentencia.get("imputados") or []:
                slug_imputado = slug_persona_minjus(imputado.get("imputado_url"), "imputado")
                if not slug_imputado:
                    continue
                relaciones.append({
                    "source_key": f"minjus_imputado:{slug_imputado}",
                    "target_key": persona_key,
                    "tipo": "TORTURO_A",
                    "fecha": fecha,
                    "fuente": origen,
                    "target_nombre": nombre,
                    "target_genero": "INDETERMINADO",
                    "target_fuente": FUENTE,
                })

    return {
        "personas": personas,
        "eventos_espaciales": eventos,
        "relaciones_interpersonales": relaciones,
        "entidades_contexto": list(entidades.values()),
        "relaciones_contexto": rel_contexto,
    }
