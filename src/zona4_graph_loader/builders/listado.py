from __future__ import annotations

from typing import Any, Dict, List

from zona4_graph_loader.domain.embarazo_norm import normalize_embarazo, parse_int
from zona4_graph_loader.domain.text_norm import clean_text


def build_listado_paginas_rows(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for page in data:
        pagina = page.get("pagina")
        if pagina is None:
            continue
        registros = page.get("registros", []) or []
        rows.append(
            {
                "pagina_key": f"listado:pagina:{pagina}",
                "pagina": pagina,
                "url": clean_text(page.get("url")),
                "registros_count": len(registros),
                "fuente": "listado_paginas",
            }
        )
    return rows


def build_listado_links_rows(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for page in data:
        pagina = page.get("pagina")
        if pagina is None:
            continue
        pagina_key = f"listado:pagina:{pagina}"
        for reg in page.get("registros", []) or []:
            registro = reg.get("registro")
            if registro is None:
                continue
            embarazo_estado, embarazo_meses = normalize_embarazo(reg.get("embarazada"))
            rows.append(
                {
                    "registro": registro,
                    "pagina_key": pagina_key,
                    "detail_url": clean_text(reg.get("detail_url")),
                    "estado_raw": clean_text(reg.get("estado")),
                    "edad": parse_int(reg.get("edad")),
                    "anio": parse_int(reg.get("año")),
                    "embarazo_estado": embarazo_estado,
                    "embarazo_meses": embarazo_meses,
                    "fuente": "listado_paginas",
                }
            )
    return rows
