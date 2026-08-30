from __future__ import annotations

from typing import Any, Dict, List

from zona4_graph_loader.builders.base import CanonicalDataset
from zona4_graph_loader.domain.text_norm import clean_text, genero_from_sexo


def build_detalles_rows(data: List[Dict[str, Any]]) -> CanonicalDataset:
    personas: List[Dict[str, Any]] = []
    for item in data:
        detalle = item.get("detalle", {})
        registro = item.get("registro")
        if registro is None:
            continue
        
        # Gender normalization (e.g. Masculino -> MASCULINO, Femenino -> FEMENINO)
        genero = genero_from_sexo(detalle.get("Sexo"))

        personas.append(
            {
                "persona_key": f"registro:{registro}",
                "registro": registro,
                "nombre": clean_text(item.get("nombre_completo")) or clean_text(detalle.get("descripcion_nombre")),
                "genero": genero,
                "fuente": "detalles_personas",
                "es_nietx": False,
                # Fix E (auditoría 2026-08-29, hallazgo I6): `Edad` existe en
                # los 8.948 registros de esta fuente y no se persistía, así
                # que una contradicción entre edad y fechas (p.ej. Edad: 25 +
                # fecha_nacimiento en 2052) quedaba invisible en el grafo. Se
                # persiste tal como la da la fuente (string), sin validar
                # contra ninguna otra fecha -sólo para que la contradicción,
                # si existe, sea auditable desde el grafo.
                "edad": clean_text(detalle.get("Edad")),
            }
        )
    return {"personas": personas}


def build_nietx_protagonistas(data: List[Dict[str, Any]]) -> CanonicalDataset:
    personas: List[Dict[str, Any]] = []
    for item in data:
        id_nietx = item.get("id_nietx")
        if id_nietx is None:
            continue

        # Fix D (auditoría 2026-08-29, hallazgo C5): `restituido.ADN` es la
        # FECHA de la confirmación genética y sólo existe en la fuente cuando
        # esa confirmación ocurrió (82 de 392 registros). Antes de este fix,
        # su ausencia se completaba con el literal "SÍ", afirmando una
        # identificación de ADN para 310 nietxs que la fuente marca como
        # todavía en búsqueda (252), no nacidxs (19), asesinadxs (4), o
        # restituidxs sin fecha de ADN registrada (35) -para un disappeared
        # person, es el peor tipo de afirmación falsa que este grafo puede
        # sostener. "DESCONOCIDA" es el sentinel que ya usa el resto del
        # cargador (fecha_sentencia, TORTURO_A.fecha) para "la fuente no lo
        # dice": no inventa una confirmación que no ocurrió, y sigue
        # satisfaciendo la restricción NOT NULL de `:Nietx.ADN`.
        restituido = item.get("restituido", {}) or {}
        adn_val = clean_text(restituido.get("ADN")) or "DESCONOCIDA"

        # `estado` es el campo que sí distingue estos casos entre sí
        # (Búsqueda / Restituido/a / No nacidx / Asesinadx) y antes de este
        # fix no se persistía en absoluto: sin él, no había forma de saber
        # desde el grafo por qué un nietx no tiene fecha de ADN. Se persiste
        # tal como lo da la fuente (no se inventa un vocabulario normalizado
        # nuevo) porque son ya cuatro strings legibles y estables.
        estado_val = clean_text(item.get("estado")) or "DESCONOCIDA"

        personas.append(
            {
                "persona_key": f"nietx:{id_nietx}",
                "nombre": clean_text(item.get("nombre_completo")),
                "genero": "INDETERMINADO",
                "fuente": "nietxs_relacion",
                "caso": clean_text(item.get("nombre_completo")) or f"Caso {id_nietx}",
                "ADN": adn_val,
                "estado": estado_val,
                "es_nietx": True,
            }
        )
    return {"personas": personas}
