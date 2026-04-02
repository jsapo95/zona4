from __future__ import annotations

from typing import Any, Dict, List

from zona4_graph_loader.domain.date_norm import parse_spanish_long_date
from zona4_graph_loader.domain.text_norm import clean_text


def build_nietx_rows(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for item in data:
        id_nietx = item.get("id_nietx")
        if id_nietx is None:
            continue
        restituido = item.get("restituido", {}) or {}
        rows.append(
            {
                "id_nietx": id_nietx,
                "nombre_caso": clean_text(item.get("nombre_completo")),
                "estado": clean_text(item.get("estado")),
                "imagen_url": clean_text(item.get("imagen_url")),
                "conoce_la_historia_url": clean_text(item.get("conoce_la_historia")),
                "resumen_data": clean_text(item.get("resumen_data")),
                "detalle_data": clean_text(item.get("detalle_data")),
                "fecha_adn": parse_spanish_long_date(clean_text(restituido.get("ADN"))),
                "fecha_restitucion": parse_spanish_long_date(clean_text(restituido.get("Restitucion")) or clean_text(restituido.get("Restitución"))),
            }
        )
    return rows
