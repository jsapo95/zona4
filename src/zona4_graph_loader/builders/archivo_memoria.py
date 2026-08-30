from __future__ import annotations

from typing import Any, Dict, List

from zona4_graph_loader.builders.base import CanonicalDataset
from zona4_graph_loader.builders.lugares import FUENTE_JERARQUIA, expand_lugar_ancestors
from zona4_graph_loader.constants import GEOREF_AMBIGUITY_DELTA, GEOREF_MIN_SCORE
from zona4_graph_loader.domain.place_norm import resolve_place
from zona4_graph_loader.domain.text_norm import clean_text

FUENTE = "archivo_memoria"
INSTITUCION_UNIVERSITARIA_KEY = "institucion:universidad_sin_especificar"


def build_archivo_memoria_rows(
    data: List[Dict[str, Any]],
    *,
    use_georef: bool = True,
) -> CanonicalDataset:
    """Convierte el Archivo de la Memoria de San Martín al CDM.

    El campo `lugar` es un topónimo corto (ej. "Billinghurst"), no una dirección
    narrativa, así que `resolve_place` lo maneja sin parsing adicional.
    """
    personas: List[Dict[str, Any]] = []
    lugares: Dict[str, Dict[str, Any]] = {}
    jerarquias: List[Dict[str, Any]] = []
    eventos: List[Dict[str, Any]] = []
    entidades: Dict[str, Dict[str, Any]] = {}
    rel_contexto: List[Dict[str, Any]] = []
    pares_parte_de: set[tuple[str, str]] = set()

    for indice, item in enumerate(data):
        nombre = clean_text(item.get("nombre"))
        if not nombre:
            continue

        persona_key = f"{FUENTE}:{indice}"
        personas.append({
            "persona_key": persona_key,
            "nombre": nombre,
            "genero": "INDETERMINADO",
            "fuente": FUENTE,
            "roles": ["VICTIMA"],
            "fecha_nacimiento": clean_text(item.get("fecha_nacimiento")),
            "fecha_secuestro": clean_text(item.get("fecha_desaparicion_normalizada")),
        })

        if item.get("estudiante_universitario"):
            entidades.setdefault(INSTITUCION_UNIVERSITARIA_KEY, {
                "entidad_key": INSTITUCION_UNIVERSITARIA_KEY,
                "tipo_entidad": "Institucion",
                "nombre": "UNIVERSIDAD SIN ESPECIFICAR",
                "fuente": FUENTE,
            })
            rel_contexto.append({
                "persona_key": persona_key,
                "entidad_key": INSTITUCION_UNIVERSITARIA_KEY,
                "tipo_relacion": "ESTUDIO_EN",
                "fecha": "DESCONOCIDA",
                "origen": FUENTE,
            })

        resuelto = resolve_place(
            item.get("lugar"),
            use_georef=use_georef,
            georef_min_score=GEOREF_MIN_SCORE,
            georef_ambiguity_delta=GEOREF_AMBIGUITY_DELTA,
        )
        if not resuelto:
            continue

        lugar_key = resuelto["lugar_key"]

        # resolve_place devuelve sólo el nodo hoja: los contenedores (provincia,
        # país) hay que materializarlos o las aristas PARTE_DE se descartan.
        # Se usa FUENTE_JERARQUIA (no FUENTE) para todo el andamiaje geográfico
        # -incluido el nodo hoja-: son geografía compartida entre fuentes (ver
        # convención en builders/lugares.py, que atribuye a "normalizacion_lugar"
        # incluso sus propios lugares resueltos), no propiedad exclusiva de
        # archivo_memoria. Sin esto, provincias y países terminan con
        # fuente="archivo_memoria" pese a anclar víctimas de todas las demás
        # fuentes.
        ancestros, saltos = expand_lugar_ancestors(lugar_key, FUENTE_JERARQUIA)
        for nodo in ancestros:
            lugares.setdefault(nodo["lugar_key"], nodo)
        lugares[lugar_key]["nombre"] = resuelto["nombre_canonico"]
        lugares[lugar_key]["tipoGeopolitico"] = resuelto["tipo"]

        for salto in saltos:
            par = (salto["child_key"], salto["parent_key"])
            if par in pares_parte_de:
                continue
            pares_parte_de.add(par)
            jerarquias.append(salto)

        eventos.append({
            "persona_key": persona_key,
            "lugar_key": lugar_key,
            "tipo_relacion": "SECUESTRADO_EN",
            "fecha": clean_text(item.get("fecha_desaparicion_normalizada")) or "DESCONOCIDA",
            "origen": FUENTE,
        })

    return {
        "personas": personas,
        "lugares": list(lugares.values()),
        "jerarquias": jerarquias,
        "eventos_espaciales": eventos,
        "entidades_contexto": list(entidades.values()),
        "relaciones_contexto": rel_contexto,
    }
