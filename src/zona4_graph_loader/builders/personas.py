from __future__ import annotations

from typing import Any, Dict, List

from zona4_graph_loader.domain.text_norm import clean_text


def build_detalles_rows(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for item in data:
        detalle = item.get("detalle", {})
        registro = item.get("registro")
        if registro is None:
            continue
        
        # Gender normalization (e.g. Masculino -> MASCULINO, Femenino -> FEMENINO)
        sexo = clean_text(detalle.get("Sexo"))
        genero = "INDETERMINADO"
        if sexo:
            if "masc" in sexo.lower():
                genero = "MASCULINO"
            elif "fem" in sexo.lower():
                genero = "FEMENINO"

        rows.append(
            {
                "persona_key": f"registro:{registro}",
                "registro": registro,
                "nombre": clean_text(item.get("nombre_completo")) or clean_text(detalle.get("descripcion_nombre")),
                "genero": genero,
                "fuente": "detalles_personas",
            }
        )
    return rows


def build_nietx_protagonistas(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for item in data:
        id_nietx = item.get("id_nietx")
        if id_nietx is None:
            continue
        
        restituido = item.get("restituido", {}) or {}
        adn_val = clean_text(restituido.get("ADN")) or "SÍ"
        
        rows.append(
            {
                "persona_key": f"nietx:{id_nietx}",
                "nombre": clean_text(item.get("nombre_completo")),
                "genero": "INDETERMINADO",
                "fuente": "nietxs_relacion",
                "caso": clean_text(item.get("nombre_completo")) or f"Caso {id_nietx}",
                "ADN": adn_val,
            }
        )
    return rows
