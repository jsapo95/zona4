from __future__ import annotations

from typing import Any, Dict, List

from zona4_graph_loader.domain.date_norm import parse_ddmmyyyy
from zona4_graph_loader.domain.text_norm import clean_text


def build_detalles_rows(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for item in data:
        detalle = item.get("detalle", {})
        registro = item.get("registro")
        if registro is None:
            continue
        rows.append(
            {
                "persona_key": f"registro:{registro}",
                "registro": registro,
                "nombre_completo": clean_text(item.get("nombre_completo")) or clean_text(detalle.get("descripcion_nombre")),
                "nombre": clean_text(item.get("nombre")),
                "apellido": clean_text(item.get("apellido")),
                "sexo": clean_text(detalle.get("Sexo")),
                "estado_desaparicion": clean_text(detalle.get("descripcion_estado")),
                "fecha_nacimiento": parse_ddmmyyyy(clean_text(detalle.get("descripcion_fecha_nacimiento"))),
                "fecha_secuestro": parse_ddmmyyyy(clean_text(detalle.get("descripcion_fecha_de_secuestro"))),
                "fecha_asesinato": parse_ddmmyyyy(clean_text(detalle.get("descripcion_fecha_de_asesinato"))),
                "lugar_nacimiento": clean_text(detalle.get("Lugar de nacimiento")),
                "lugar_secuestro": clean_text(detalle.get("descripcion_lugar_de_secuestro")),
                "fuentes": ["detalles_personas"],
            }
        )
    return rows


def build_nietx_protagonistas(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for item in data:
        id_nietx = item.get("id_nietx")
        if id_nietx is None:
            continue
        rows.append(
            {
                "id_nietx": id_nietx,
                "persona_key": f"nietx:{id_nietx}",
                "nombre_completo": clean_text(item.get("nombre_completo")),
                "fuentes": ["nietxs_relacion"],
            }
        )
    return rows
