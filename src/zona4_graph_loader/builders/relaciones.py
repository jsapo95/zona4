from __future__ import annotations

from typing import Any, Dict, List

from zona4_graph_loader.builders.base import CanonicalDataset
from zona4_graph_loader.domain.text_norm import clean_text, persona_key_from_name


def _map_relation(
    source_key: str,
    source_name: str,
    target_key: str,
    target_name: str,
    raw_rel: str,
    fuente: str,
) -> List[Dict[str, Any]]:
    rel = (raw_rel or "").strip().lower()
    rows = []

    # Map raw relations to strict V1.1/V1.1.1 relationship labels and directions
    if rel == "madre":
        # target is mother of source: target -[:MADRE_DE]-> source
        rows.append({
            "source_key": target_key,
            "source_nombre": target_name,
            "target_key": source_key,
            "target_nombre": source_name,
            "tipo": "MADRE_DE",
            "fuente": fuente,
            "fecha": "DESCONOCIDA",
        })
    elif rel == "padre":
        # target is father of source: target -[:PADRE_DE]-> source
        rows.append({
            "source_key": target_key,
            "source_nombre": target_name,
            "target_key": source_key,
            "target_nombre": source_name,
            "tipo": "PADRE_DE",
            "fuente": fuente,
            "fecha": "DESCONOCIDA",
        })
    elif rel in ("hijo", "hija"):
        # target is child of source: target -[:HIJE_DE]-> source
        rows.append({
            "source_key": target_key,
            "source_nombre": target_name,
            "target_key": source_key,
            "target_nombre": source_name,
            "tipo": "HIJE_DE",
            "fuente": fuente,
            "fecha": "DESCONOCIDA",
        })
    elif "abuela" in rel:
        # target is grandparent of source: target -[:ABUELX_DE]-> source
        rows.append({
            "source_key": target_key,
            "source_nombre": target_name,
            "target_key": source_key,
            "target_nombre": source_name,
            "tipo": "ABUELX_DE",
            "fuente": fuente,
            "fecha": "DESCONOCIDA",
        })
    elif rel in ("hermano", "hermana", "hermanx"):
        # source is sibling of target: source -[:HERMANX_DE]-> target
        rows.append({
            "source_key": source_key,
            "source_nombre": source_name,
            "target_key": target_key,
            "target_nombre": target_name,
            "tipo": "HERMANX_DE",
            "fuente": fuente,
            "fecha": "DESCONOCIDA",
        })
    elif rel in ("esposo", "esposa", "conyuge", "pareja", "companero", "companera", "novio", "novia", "ex esposa", "ex esposo"):
        # source is partner of target: source -[:PAREJA_DE]-> target
        rows.append({
            "source_key": source_key,
            "source_nombre": source_name,
            "target_key": target_key,
            "target_nombre": target_name,
            "tipo": "PAREJA_DE",
            "fuente": fuente,
            "fecha": "DESCONOCIDA",
        })
    elif rel in ("cunado", "cunada", "cuñado", "cuñada"):
        # source is brother/sister-in-law of target: source -[:CUÑADX_DE]-> target
        rows.append({
            "source_key": source_key,
            "source_nombre": source_name,
            "target_key": target_key,
            "target_nombre": target_name,
            "tipo": "CUÑADX_DE",
            "fuente": fuente,
            "fecha": "DESCONOCIDA",
        })
    elif rel in ("suegro", "suegra"):
        # target is parent-in-law of source: target -[:SUEGRX_DE]-> source
        rows.append({
            "source_key": target_key,
            "source_nombre": target_name,
            "target_key": source_key,
            "target_nombre": source_name,
            "tipo": "SUEGRX_DE",
            "fuente": fuente,
            "fecha": "DESCONOCIDA",
        })
    elif rel in ("yerno", "nuera"):
        # target is child-in-law of source: target -[:YERNX_NUERX_DE]-> source
        rows.append({
            "source_key": target_key,
            "source_nombre": target_name,
            "target_key": source_key,
            "target_nombre": source_name,
            "tipo": "YERNX_NUERX_DE",
            "fuente": fuente,
            "fecha": "DESCONOCIDA",
        })

    return rows


def build_nietx_rel_rows(data: List[Dict[str, Any]]) -> CanonicalDataset:
    relaciones: List[Dict[str, Any]] = []
    for item in data:
        id_nietx = item.get("id_nietx")
        if id_nietx is None:
            continue
        source_key = f"nietx:{id_nietx}"
        source_name = clean_text(item.get("nombre_completo")) or f"Nietx {id_nietx}"

        for rel in item.get("relaciones", []) or []:
            rel_name = clean_text(rel.get("nombre_completo_relacion"))
            if not rel_name:
                continue
            rel_id = rel.get("id_persona")
            target_key = f"registro:{rel_id}" if rel_id is not None else persona_key_from_name(rel_name)
            
            raw_rel = clean_text(rel.get("relacion"))
            relaciones.extend(
                _map_relation(
                    source_key=source_key,
                    source_name=source_name,
                    target_key=target_key,
                    target_name=rel_name,
                    raw_rel=raw_rel,
                    fuente="nietxs_relacion",
                )
            )
    return {"relaciones_interpersonales": relaciones}


def build_detalles_rel_rows(data: List[Dict[str, Any]]) -> CanonicalDataset:
    relaciones: List[Dict[str, Any]] = []
    for item in data:
        registro = item.get("registro")
        if registro is None:
            continue
        source_key = f"registro:{registro}"
        source_name = clean_text(item.get("nombre_completo")) or f"Registro {registro}"

        detalle = item.get("detalle", {})
        for rel in detalle.get("victimas_relacionadas_red", []) or []:
            rel_name = clean_text(rel.get("nombre_completo"))
            if not rel_name:
                continue
            rel_id = rel.get("registro")
            target_key = f"registro:{rel_id}" if rel_id is not None else persona_key_from_name(rel_name)
            
            raw_rel = clean_text(rel.get("relacion"))
            relaciones.extend(
                _map_relation(
                    source_key=source_key,
                    source_name=source_name,
                    target_key=target_key,
                    target_name=rel_name,
                    raw_rel=raw_rel,
                    fuente="detalles_personas",
                )
            )
    return {"relaciones_interpersonales": relaciones}
