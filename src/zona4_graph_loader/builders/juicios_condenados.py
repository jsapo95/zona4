from __future__ import annotations

import re
from datetime import date
from typing import Any, Dict, List, Optional

from zona4_graph_loader.builders.base import CanonicalDataset
from zona4_graph_loader.constants import SENTINEL_ORG_VALUES
from zona4_graph_loader.domain.date_norm import validar_fecha_de_nacimiento
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

        fuerza = clean_text(datos.get("Fuerza"))
        fuerza_upper = fuerza.upper() if fuerza else None

        personas.append({
            "persona_key": persona_key,
            "nombre": nombre,
            "genero": "INDETERMINADO",
            "fuente": FUENTE,
            "roles": sorted(roles),
            "complice_tipo": complice_tipo,
            # Fix E (auditoría 2026-08-29, hallazgo I6): mismo guardia que en
            # minjus_imputados.py; sobre los datos reales de esta fuente no
            # hay ningún valor fuera de rango hoy (1923-1979), pero se aplica
            # igual para que la invariante ("ninguna fecha_nacimiento después
            # de 1983") valga para todo el grafo, no sólo donde ya se
            # encontró el defecto.
            "fecha_nacimiento": validar_fecha_de_nacimiento(_parse_nacimiento(datos.get("Nacimiento"))),
            # Fix E (auditoría 2026-08-29, hallazgo I3d): se persiste el
            # valor crudo de `Fuerza` en la persona incluso cuando es un
            # sentinel ("SIN ESPECIFICAR", "CIVIL") y por eso no genera
            # :Org/PARTE_DE más abajo -el dato ("no se sabe la fuerza" /
            # "era civil") no se pierde, sólo deja de fabricar una
            # organización falsa para sostenerlo.
            "fuerza": fuerza_upper,
        })

        if not fuerza_upper or fuerza_upper in SENTINEL_ORG_VALUES:
            # Fix E (hallazgo I3d): "SIN ESPECIFICAR" / "CIVIL" / etc. no son
            # organizaciones -son la ausencia de un dato o la ausencia misma
            # de fuerza represiva. Materializarlas como :Org agrupa a
            # cientos de represores distintos bajo una membresía compartida
            # falsa (109 casos reales de "SIN ESPECIFICAR", 87 de "CIVIL",
            # combinando esta fuente con minjus_imputados).
            continue
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
