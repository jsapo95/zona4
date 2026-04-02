from __future__ import annotations

from typing import Any, Dict, List

from zona4_graph_loader.domain.relation_norm import normalize_relation
from zona4_graph_loader.domain.text_norm import clean_text, persona_key_from_name


def build_nietx_rel_rows(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for item in data:
        id_nietx = item.get("id_nietx")
        if id_nietx is None:
            continue
        source_key = f"nietx:{id_nietx}"
        for rel in item.get("relaciones", []) or []:
            rel_name = clean_text(rel.get("nombre_completo_relacion"))
            if not rel_name:
                continue
            rel_id = rel.get("id_persona")
            target_key = f"registro:{rel_id}" if rel_id is not None else persona_key_from_name(rel_name)
            rows.append(
                {
                    "source_key": source_key,
                    "target_key": target_key,
                    "target_registro": rel_id,
                    "target_nombre": rel_name,
                    "target_placeholder": rel_id is None,
                    "tipo_raw": clean_text(rel.get("relacion")),
                    "tipo": normalize_relation(clean_text(rel.get("relacion"))),
                    "fuente": "nietxs_relacion",
                }
            )
    return rows


def build_detalles_rel_rows(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for item in data:
        registro = item.get("registro")
        if registro is None:
            continue
        source_key = f"registro:{registro}"
        detalle = item.get("detalle", {})
        for rel in detalle.get("victimas_relacionadas_red", []) or []:
            rel_name = clean_text(rel.get("nombre_completo"))
            if not rel_name:
                continue
            rel_id = rel.get("registro")
            target_key = f"registro:{rel_id}" if rel_id is not None else persona_key_from_name(rel_name)
            rows.append(
                {
                    "source_key": source_key,
                    "target_key": target_key,
                    "target_registro": rel_id,
                    "target_nombre": rel_name,
                    "target_placeholder": rel_id is None,
                    "tipo_raw": clean_text(rel.get("relacion")),
                    "tipo": normalize_relation(clean_text(rel.get("relacion"))),
                    "fuente": "detalles_personas",
                }
            )
    return rows


def build_detalles_simult_rows(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for item in data:
        registro = item.get("registro")
        if registro is None:
            continue
        source_key = f"registro:{registro}"
        detalle = item.get("detalle", {})
        for rel in detalle.get("victimas_simultaneas_red", []) or []:
            rel_name = clean_text(rel.get("nombre_completo"))
            if not rel_name:
                continue
            rel_id = rel.get("registro")
            target_key = f"registro:{rel_id}" if rel_id is not None else persona_key_from_name(rel_name)
            rows.append(
                {
                    "source_key": source_key,
                    "target_key": target_key,
                    "target_registro": rel_id,
                    "target_nombre": rel_name,
                    "target_placeholder": rel_id is None,
                    "fuente": "detalles_personas",
                }
            )
    return rows
