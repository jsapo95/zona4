from __future__ import annotations

import re
from typing import Any, Dict, Optional

from zona4_graph_loader.constants import EQUIV_CITIES, PROVINCE_ABBR, UNKNOWN_PLACE_VALUES
from zona4_graph_loader.domain.text_norm import clean_text, norm_space, slugify_name, strip_accents


def normalize_place_text(value: str) -> str:
    text = strip_accents(value.upper())
    text = re.sub(r"[^A-Z0-9\s]", " ", text)
    text = norm_space(text)
    return text


def normalize_place_identity(value: str) -> str:
    text = value
    text = re.sub(r"\bCDAD\b", "CIUDAD", text)
    text = re.sub(r"\bCAP\s+FED\b", "CAPITAL FEDERAL", text)
    text = re.sub(r"\bSTA\b", "SANTA", text)
    text = re.sub(r"\bSECUETRADO\b", "SECUESTRADO", text)
    text = re.sub(r"\bSECUESTRAD[OA]S?\b", "SECUESTRADO", text)
    text = re.sub(r"\bFUE\s+SECUESTRADO\b", "SECUESTRADO", text)
    text = re.sub(r"\bDE\s+SU\s+DOMICILIO\b", "", text)
    text = re.sub(r"\bEN\s+SU\s+DOMICILIO\b", "", text)
    return norm_space(text)


def make_lugar_key(tipo: str, nombre: str, parent_key: Optional[str]) -> str:
    base = f"lugar:{tipo}:{slugify_name(nombre)}"
    return f"{base}|{parent_key}" if parent_key else base


def resolve_place(raw: Optional[str]) -> Optional[Dict[str, Any]]:
    text = clean_text(raw)
    if text is None:
        return None

    alias_norm = normalize_place_identity(normalize_place_text(text))
    if not alias_norm or alias_norm in UNKNOWN_PLACE_VALUES:
        return None

    if alias_norm in EQUIV_CITIES:
        tipo, nombre, parent_name = EQUIV_CITIES[alias_norm]
        parent_key = None
        if parent_name:
            parent_key = make_lugar_key("PROVINCIA", parent_name, "lugar:PAIS:argentina")
        lugar_key = make_lugar_key(tipo, nombre, parent_key)
        return {
            "alias_raw": text,
            "alias_norm": alias_norm,
            "tipo": tipo,
            "nombre_canonico": nombre,
            "lugar_key": lugar_key,
            "parent_key": parent_key,
        }

    for suffix, prov_name in PROVINCE_ABBR.items():
        if alias_norm.endswith(f" {suffix}"):
            city_name = alias_norm[: -len(suffix)].strip()
            if city_name:
                parent_key = make_lugar_key("PROVINCIA", prov_name, "lugar:PAIS:argentina")
                lugar_key = make_lugar_key("CIUDAD", city_name, parent_key)
                return {
                    "alias_raw": text,
                    "alias_norm": alias_norm,
                    "tipo": "CIUDAD",
                    "nombre_canonico": city_name,
                    "lugar_key": lugar_key,
                    "parent_key": parent_key,
                }

    lugar_key = make_lugar_key("INDETERMINADO", alias_norm, None)
    return {
        "alias_raw": text,
        "alias_norm": alias_norm,
        "tipo": "INDETERMINADO",
        "nombre_canonico": alias_norm,
        "lugar_key": lugar_key,
        "parent_key": None,
    }
