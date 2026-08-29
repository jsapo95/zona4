from __future__ import annotations

from typing import Any, Dict, List, Optional

from zona4_graph_loader.builders.base import CanonicalDataset
from zona4_graph_loader.builders.minjus_sentencias import FUENTE as FUENTE_SENTENCIAS
from zona4_graph_loader.builders.minjus_sentencias import (
    FUENTE_TORTURO_A_SIN_SENTENCIA,
    slug_sentencia,
)
from zona4_graph_loader.domain.date_norm import parse_ddmmyyyy
from zona4_graph_loader.domain.text_norm import clean_text, slugify_name

FUENTE = "minjus_imputados"


def slug_persona_minjus(url: Optional[str], prefijo: str) -> Optional[str]:
    text = clean_text(url)
    if text is None:
        return None
    marcador = f"/{prefijo}/"
    if marcador in text:
        text = text.split(marcador, 1)[1]
    return text.strip("/") or None


def build_minjus_imputados_rows(
    data: List[Dict[str, Any]],
    *,
    sentencias_index: Dict[str, Dict[str, Any]],
) -> CanonicalDataset:
    """Convierte los imputados de MinJus GBA al CDM.

    Las aristas TORTURO_A apuntan a `minjus_victima:{slug}`, las mismas claves que
    genera el builder de víctimas, de modo que la reconciliación no tenga que
    inventar placeholders.
    """
    personas: List[Dict[str, Any]] = []
    relaciones: List[Dict[str, Any]] = []
    entidades: Dict[str, Dict[str, Any]] = {}
    rel_contexto: List[Dict[str, Any]] = []

    for item in data:
        slug = slug_persona_minjus(item.get("source_url"), "imputado")
        nombre = clean_text(item.get("nombre"))
        if not slug or not nombre:
            continue

        persona_key = f"minjus_imputado:{slug}"
        datos = item.get("datos_personales") or {}

        personas.append({
            "persona_key": persona_key,
            "nombre": nombre,
            "genero": "INDETERMINADO",
            "fuente": FUENTE,
            "roles": ["REPRESOR"],
            "fecha_nacimiento": parse_ddmmyyyy(clean_text(datos.get("fecha_de_nacimiento"))),
        })

        fuerza = clean_text(datos.get("fuerza"))
        if fuerza:
            fuerza_upper = fuerza.upper()
            entidad_key = f"org:{slugify_name(fuerza_upper)}"
            entidades.setdefault(entidad_key, {
                "entidad_key": entidad_key,
                "tipo_entidad": "Org",
                "nombre": fuerza_upper,
                "tipoOrg": "FUERZA",
                "fuente": FUENTE,
            })
            rel_contexto.append({
                "persona_key": persona_key,
                "entidad_key": entidad_key,
                "tipo_relacion": "PARTE_DE",
                "fecha": "DESCONOCIDA",
                "origen": FUENTE,
            })

        apodo = clean_text(datos.get("apodo"))
        if apodo:
            alias_key = f"alias_persona:{slugify_name(apodo)}|{slug}"
            entidades.setdefault(alias_key, {
                "entidad_key": alias_key,
                "tipo_entidad": "AliasPersona",
                "alias": apodo,
                "fuente": FUENTE,
            })
            rel_contexto.append({
                "persona_key": persona_key,
                "entidad_key": alias_key,
                "tipo_relacion": "IDENTIFICA_A",
                "fecha": "DESCONOCIDA",
                "origen": FUENTE,
            })

        for bloque in item.get("sentencias_y_victimas") or []:
            slug_sent = slug_sentencia(bloque.get("sentencia_url"))
            meta = sentencias_index.get(slug_sent or "")
            if meta:
                origen = meta["origen"]
                fecha = meta.get("fecha") or "DESCONOCIDA"
            elif slug_sent:
                # Slug real pero fuera del índice (sentencia no encontrada en el
                # archivo de sentencias). Se deriva del propio slug, no de un
                # literal por-builder, para que el mismo hecho compartido con el
                # builder de víctimas produzca el mismo `fuente` aunque el índice
                # cambie entre corridas.
                origen = f"{FUENTE_SENTENCIAS}:{slug_sent}"
                fecha = "DESCONOCIDA"
            else:
                origen = FUENTE_TORTURO_A_SIN_SENTENCIA
                fecha = "DESCONOCIDA"

            for victima in bloque.get("victimas_asociadas") or []:
                slug_victima = slug_persona_minjus(victima.get("victima_url"), "victima")
                if not slug_victima:
                    continue
                relaciones.append({
                    "source_key": persona_key,
                    "target_key": f"minjus_victima:{slug_victima}",
                    "tipo": "TORTURO_A",
                    "fecha": fecha,
                    "fuente": origen,
                    "target_nombre": clean_text(victima.get("victima_nombre")),
                    "target_genero": "INDETERMINADO",
                    "target_fuente": "minjus_victimas",
                })

    return {
        "personas": personas,
        "relaciones_interpersonales": relaciones,
        "entidades_contexto": list(entidades.values()),
        "relaciones_contexto": rel_contexto,
    }
