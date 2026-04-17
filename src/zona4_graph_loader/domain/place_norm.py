from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import re
from typing import Any, Dict, Optional

from zona4_graph_loader.constants import (
    EQUIV_CITIES,
    GEOREF_AMBIGUITY_DELTA,
    GEOREF_CATALOG_PATH,
    GEOREF_MIN_SCORE,
    PROVINCE_ABBR,
    UNKNOWN_PLACE_VALUES,
)
from zona4_graph_loader.domain.place_gazetteer import PlaceGazetteer
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
    text = re.sub(r"\bVIA\s+PUBLICA\b", "", text)
    text = re.sub(r"\bDOMICILIO\s+PARTICULAR\b", "", text)
    text = re.sub(r"\bSECUESTRADO\b", "", text)
    text = re.sub(r"\bASESINAD[OA]S?\b", "", text)
    text = re.sub(r"\bNO\s+CONSTA\b", "", text)
    return norm_space(text)


def make_lugar_key(tipo: str, nombre: str, parent_key: Optional[str]) -> str:
    base = f"lugar:{tipo}:{slugify_name(nombre)}"
    return f"{base}|{parent_key}" if parent_key else base


@lru_cache(maxsize=4)
def _load_georef_resolver(catalog_path: str) -> Optional[PlaceGazetteer]:
    path = Path(catalog_path)
    if not path.is_absolute():
        path = Path.cwd() / path
    if not path.exists():
        return None
    return PlaceGazetteer.from_file(path)


def _resolve_with_georef(alias_norm: str, resolver: PlaceGazetteer, min_score: float, ambiguity_delta: float) -> Optional[Dict[str, Any]]:
    match = resolver.resolve(alias_norm, min_score=min_score, ambiguity_delta=ambiguity_delta)
    if not match:
        return None

    if match.level == "PROVINCIA":
        lugar_key = make_lugar_key("PROVINCIA", match.name, "lugar:PAIS:argentina")
        return {
            "alias_norm": alias_norm,
            "tipo": "PROVINCIA",
            "nombre_canonico": match.name,
            "lugar_key": lugar_key,
            "parent_key": "lugar:PAIS:argentina",
        }

    parent_key = make_lugar_key("PROVINCIA", match.provincia_name, "lugar:PAIS:argentina")
    city_like = "CIUDAD" if match.level in {"LOCALIDAD", "MUNICIPIO"} else "DEPARTAMENTO"
    lugar_key = make_lugar_key(city_like, match.name, parent_key)
    return {
        "alias_norm": alias_norm,
        "tipo": city_like,
        "nombre_canonico": match.name,
        "lugar_key": lugar_key,
        "parent_key": parent_key,
    }


def _resolve_caba(alias_norm: str) -> Optional[Dict[str, Any]]:
    hints = (
        "CAPITAL FEDERAL",
        " CABA ",
        "CIUDAD DE BUENOS AIRES",
        "CIUDAD AUTONOMA DE BUENOS AIRES",
    )
    padded = f" {alias_norm} "
    if not any(hint in padded for hint in hints):
        return None

    lugar_key = make_lugar_key("CIUDAD", "CIUDAD AUTONOMA DE BUENOS AIRES", None)
    return {
        "alias_norm": alias_norm,
        "tipo": "CIUDAD",
        "nombre_canonico": "CIUDAD AUTONOMA DE BUENOS AIRES",
        "lugar_key": lugar_key,
        "parent_key": None,
    }


def resolve_place(
    raw: Optional[str],
    *,
    use_georef: bool = True,
    georef_catalog_path: Path = GEOREF_CATALOG_PATH,
    georef_min_score: float = GEOREF_MIN_SCORE,
    georef_ambiguity_delta: float = GEOREF_AMBIGUITY_DELTA,
) -> Optional[Dict[str, Any]]:
    text = clean_text(raw)
    if text is None:
        return None

    alias_norm = normalize_place_identity(normalize_place_text(text))
    if not alias_norm or alias_norm in UNKNOWN_PLACE_VALUES:
        return None

    if use_georef:
        resolver = _load_georef_resolver(str(georef_catalog_path))
        if resolver is not None:
            georef_resolved = _resolve_with_georef(
                alias_norm,
                resolver,
                min_score=georef_min_score,
                ambiguity_delta=georef_ambiguity_delta,
            )
            if georef_resolved is not None:
                georef_resolved["alias_raw"] = text
                return georef_resolved

    caba_resolved = _resolve_caba(alias_norm)
    if caba_resolved is not None:
        caba_resolved["alias_raw"] = text
        return caba_resolved

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
