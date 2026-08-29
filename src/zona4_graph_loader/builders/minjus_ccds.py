from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from zona4_graph_loader.builders.base import CanonicalDataset
from zona4_graph_loader.domain.name_similarity import name_similarity_score
from zona4_graph_loader.domain.text_norm import clean_text, slugify_name, strip_accents

FUENTE = "minjus_ccds"
DEDUP_THRESHOLD = 0.93

_DIGITS_RE = re.compile(r"\d+")


def slug_ccd(url: Optional[str]) -> Optional[str]:
    """El dataset alterna entre /centrodedetencion/ y /centrodetencion/."""
    text = clean_text(url)
    if text is None:
        return None
    for marcador in ("/centrodedetencion/", "/centrodetencion/"):
        if marcador in text:
            text = text.split(marcador, 1)[1]
            break
    return text.strip("/") or None


def _numeros_distintos(nombre_a: str, nombre_b: str) -> bool:
    """True si ambos nombres traen numeros y esos numeros no coinciden.

    `name_similarity_score` descarta los tokens de un solo caracter como ruido
    (via `_remove_trash` en `domain/name_similarity.py`), lo que incluye
    numeros de un digito. Eso significa que su chequeo interno de
    "numeros distintos -> score 0" nunca se activa para designadores como
    "Comisaria 5ta" vs "Comisaria 8va": ambos terminan con el mismo conjunto de
    tokens y el score da 1.0. Contra los datos reales de MinJus esto fusiona
    comisarias distintas (5ta, 8va, 1ra, 2da, 3ra de la misma localidad) en un
    solo nodo de RUVTE. Este chequeo adicional, sobre los digitos crudos del
    nombre (antes de tokenizar), evita ese falso positivo sin tocar la funcion
    compartida que usan otros builders para nombres de personas.
    """
    numeros_a = set(_DIGITS_RE.findall(nombre_a))
    numeros_b = set(_DIGITS_RE.findall(nombre_b))
    return bool(numeros_a) and bool(numeros_b) and numeros_a != numeros_b


def _match_existente(nombre_upper: str, existing_ccds: Dict[str, str]) -> Optional[str]:
    sin_acentos = strip_accents(nombre_upper)
    directo = existing_ccds.get(sin_acentos) or existing_ccds.get(nombre_upper)
    if directo:
        return directo
    mejor_key, mejor_score = None, 0.0
    for nombre_existente, lugar_key in existing_ccds.items():
        if _numeros_distintos(nombre_upper, nombre_existente):
            continue
        score = name_similarity_score(sin_acentos, strip_accents(nombre_existente))
        if score > mejor_score:
            mejor_key, mejor_score = lugar_key, score
    return mejor_key if mejor_score >= DEDUP_THRESHOLD else None


def build_minjus_ccds_rows(
    data: List[Dict[str, Any]],
    *,
    existing_ccds: Optional[Dict[str, str]] = None,
) -> Tuple[CanonicalDataset, Dict[str, str]]:
    """Convierte los CCDs de MinJus GBA al CDM y devuelve el mapa slug -> lugar_key.

    El mapa es lo que consumen los builders de victimas e imputados para colgar
    aristas PRESENTE_EN sin recurrir al texto libre.

    `existing_ccds` mapea nombre en mayusculas -> lugar_key de los CCDs ya
    cargados (RUVTE). Cuando hay match fuerte se reutiliza esa clave y no se
    crea un nodo nuevo, para no duplicar el mismo centro con dos origenes.
    """
    existing_ccds = existing_ccds or {}
    lugares: Dict[str, Dict[str, Any]] = {}
    direcciones: Dict[str, Dict[str, Any]] = {}
    jerarquias: List[Dict[str, Any]] = []
    key_by_slug: Dict[str, str] = {}

    for item in data:
        slug = slug_ccd(item.get("source_url"))
        titulo = clean_text(item.get("titulo"))
        if not slug or not titulo:
            continue

        nombre_upper = titulo.upper()
        reutilizada = _match_existente(nombre_upper, existing_ccds)
        if reutilizada:
            key_by_slug[slug] = reutilizada
            continue

        lugar_key = f"lugar:CCD:{slugify_name(slug)}"
        key_by_slug[slug] = lugar_key
        metadatos = item.get("metadatos") or {}

        lugares[lugar_key] = {
            "lugar_key": lugar_key,
            "nombre": nombre_upper,
            "tipoGeopolitico": "CCD",
            "pais_code": "AR",
            "fuente": FUENTE,
            "jurisdiccion": clean_text(metadatos.get("Dependencia")),
            "ubicacion": clean_text(metadatos.get("Domicilio")),
            "tipo_entidad": "Lugar",
        }

        domicilio = clean_text(metadatos.get("Domicilio"))
        if domicilio:
            direccion_key = f"direccion_ccd:minjus:{slugify_name(slug)}"
            direcciones[direccion_key] = {
                "direccion_ccd_key": direccion_key,
                "coordenadas": "DESCONOCIDAS",
                "direccionExacta": domicilio,
                "lugar_key": lugar_key,
                "tipo_entidad": "DireccionCCD",
            }
            jerarquias.append({
                "tipo_relacion": "UBICADA_EN",
                "direccion_ccd_key": direccion_key,
                "lugar_key": lugar_key,
            })

    dataset: CanonicalDataset = {
        "lugares": list(lugares.values()) + list(direcciones.values()),
        "jerarquias": jerarquias,
    }
    return dataset, key_by_slug
