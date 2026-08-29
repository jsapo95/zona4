from __future__ import annotations

import re
from datetime import date
from typing import Any, Dict, List, Optional

from zona4_graph_loader.builders.base import CanonicalDataset
from zona4_graph_loader.domain.text_norm import clean_text, slugify_name

FUENTE = "juicios_condenados"

# El dataset clasifica en FUERZAS ARMADAS, FUERZAS DE SEGURIDAD y CIVILES.
# Los civiles condenados por lesa humanidad son cómplices civiles en el modelo.
CATEGORIA_CIVIL = "CIVILES"


def _parse_nacimiento(value: Any) -> Optional[str]:
    """El campo Nacimiento viene como DD-MM-YYYY, distinto del DD/MM/YYYY de MinJus.

    Para condenados fallecidos el dato real trae "DD-MM-YYYY/DD-MM-YYYY"
    (nacimiento/fallecimiento, en ese orden); sólo nos interesa el primer
    componente.
    """
    text = clean_text(value)
    if text is None:
        return None
    primero = text.split("/", 1)[0].strip()
    match = re.fullmatch(r"(\d{2})-(\d{2})-(\d{4})", primero)
    if not match:
        return None
    day, month, year = map(int, match.groups())
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def build_juicios_condenados_rows(payload: Dict[str, Any]) -> CanonicalDataset:
    personas: List[Dict[str, Any]] = []
    entidades: Dict[str, Dict[str, Any]] = {}
    rel_contexto: List[Dict[str, Any]] = []

    registros = (payload.get("resultado") or {}).get("condenado") or []

    for registro in registros:
        datos = registro.get("condenados") or {}
        impu_id = datos.get("impu_id")
        nombre = clean_text(datos.get("apellido_nombre"))
        if impu_id is None or not nombre:
            continue

        persona_key = f"juicios_condenado:{impu_id}"
        categoria = (clean_text(datos.get("Categoria")) or "").upper()
        roles = ["REPRESOR"]
        complice_tipo = None
        if categoria == CATEGORIA_CIVIL:
            roles.append("COMPLICE")
            complice_tipo = "CIVIL"

        personas.append({
            "persona_key": persona_key,
            "nombre": nombre,
            "genero": "INDETERMINADO",
            "fuente": FUENTE,
            "roles": sorted(roles),
            "complice_tipo": complice_tipo,
            "fecha_nacimiento": _parse_nacimiento(datos.get("Nacimiento")),
        })

        fuerza = clean_text(datos.get("Fuerza"))
        if not fuerza:
            continue
        fuerza_upper = fuerza.upper()
        entidad_key = f"org:{slugify_name(fuerza_upper)}"
        entidades.setdefault(entidad_key, {
            "entidad_key": entidad_key,
            "tipo_entidad": "Org",
            "nombre": fuerza_upper,
            "tipoOrg": "FUERZA",
            "fuente": FUENTE,
        })
        rel_contexto.append({
            "persona_key": persona_key,
            "entidad_key": entidad_key,
            "tipo_relacion": "PARTE_DE",
            "fecha": "DESCONOCIDA",
            "origen": FUENTE,
        })

    return {
        "personas": personas,
        "entidades_contexto": list(entidades.values()),
        "relaciones_contexto": rel_contexto,
    }
