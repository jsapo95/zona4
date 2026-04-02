from __future__ import annotations

from typing import Any, Dict, List

from zona4_graph_loader.domain.date_norm import parse_ddmmyyyy, parse_spanish_long_date
from zona4_graph_loader.domain.text_norm import clean_text


def build_detalles_event_rows(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for item in data:
        registro = item.get("registro")
        if registro is None:
            continue

        detalle = item.get("detalle", {})

        fecha_sec_raw = clean_text(detalle.get("descripcion_fecha_de_secuestro"))
        lugar_sec = clean_text(detalle.get("descripcion_lugar_de_secuestro"))
        if fecha_sec_raw or lugar_sec:
            rows.append(
                {
                    "evento_key": f"evento:detalles:secuestro:{registro}",
                    "tipo": "SECUESTRO",
                    "fecha": parse_ddmmyyyy(fecha_sec_raw),
                    "lugar": lugar_sec,
                    "descripcion_raw": fecha_sec_raw,
                    "fuente": "detalles_personas",
                    "persona_key": f"registro:{registro}",
                    "rol": "victima",
                }
            )

        fecha_ase_raw = clean_text(detalle.get("descripcion_fecha_de_asesinato"))
        lugar_ase = clean_text(detalle.get("Lugar de asesinato"))
        if fecha_ase_raw or lugar_ase:
            rows.append(
                {
                    "evento_key": f"evento:detalles:asesinato:{registro}",
                    "tipo": "ASESINATO",
                    "fecha": parse_ddmmyyyy(fecha_ase_raw),
                    "lugar": lugar_ase,
                    "descripcion_raw": fecha_ase_raw,
                    "fuente": "detalles_personas",
                    "persona_key": f"registro:{registro}",
                    "rol": "victima",
                }
            )
    return rows


def build_nietx_event_rows(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for item in data:
        id_nietx = item.get("id_nietx")
        if id_nietx is None:
            continue

        restituido = item.get("restituido", {}) or {}
        fecha_adn_raw = clean_text(restituido.get("ADN"))
        fecha_rest_raw = clean_text(restituido.get("Restitucion")) or clean_text(restituido.get("Restitución"))

        if fecha_adn_raw:
            rows.append(
                {
                    "evento_key": f"evento:nietx:adn:{id_nietx}",
                    "tipo": "ADN",
                    "fecha": parse_spanish_long_date(fecha_adn_raw),
                    "lugar": None,
                    "descripcion_raw": fecha_adn_raw,
                    "fuente": "nietxs_relacion",
                    "persona_key": f"nietx:{id_nietx}",
                    "id_nietx": id_nietx,
                    "rol": "protagonista",
                }
            )

        if fecha_rest_raw:
            rows.append(
                {
                    "evento_key": f"evento:nietx:restitucion:{id_nietx}",
                    "tipo": "RESTITUCION",
                    "fecha": parse_spanish_long_date(fecha_rest_raw),
                    "lugar": None,
                    "descripcion_raw": fecha_rest_raw,
                    "fuente": "nietxs_relacion",
                    "persona_key": f"nietx:{id_nietx}",
                    "id_nietx": id_nietx,
                    "rol": "protagonista",
                }
            )

    return rows
