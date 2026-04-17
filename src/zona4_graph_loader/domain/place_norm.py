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


FOREIGN_COUNTRY_EQUIV: Dict[str, tuple[str, str]] = {
    "PARAGUAY": ("PARAGUAY", "PY"),
    "CHILE": ("CHILE", "CL"),
    "ITALIA": ("ITALIA", "IT"),
    "BOLIVIA": ("BOLIVIA", "BO"),
    "ESPANA": ("ESPANA", "ES"),
    "BRASIL": ("BRASIL", "BR"),
    "URUGUAY": ("URUGUAY", "UY"),
    "FRANCIA": ("FRANCIA", "FR"),
    "MEXICO": ("MEXICO", "MX"),
    "COLOMBIA": ("COLOMBIA", "CO"),
    "VENEZUELA": ("VENEZUELA", "VE"),
    "ALEMANIA": ("ALEMANIA", "DE"),
    "BELGICA": ("BELGICA", "BE"),
    "AUSTRIA": ("AUSTRIA", "AT"),
    "HONDURAS": ("HONDURAS", "HN"),
    "PERU": ("PERU", "PE"),
    "ESTADOS UNIDOS": ("ESTADOS UNIDOS", "US"),
    "CUBA": ("CUBA", "CU"),
    "CHECOSLOVAQUIA": ("CHECOSLOVAQUIA", "CS"),
    "PORTUGAL": ("PORTUGAL", "PT"),
    "SUECIA": ("SUECIA", "SE"),
    "SUIZA": ("SUIZA", "CH"),
    "MARRUECOS": ("MARRUECOS", "MA"),
    "GRECIA": ("GRECIA", "GR"),
    "POLONIA": ("POLONIA", "PL"),
    "GUATEMALA": ("GUATEMALA", "GT"),
    "CROACIA": ("CROACIA", "HR"),
    "YUGOSLAVIA": ("YUGOSLAVIA", "YU"),
}

FOREIGN_CITY_COUNTRY_EQUIV: Dict[str, tuple[str, str]] = {
    "ASUNCION PARAGUAY": ("ASUNCION", "PARAGUAY"),
    "RIO DE JANEIRO BRASIL": ("RIO DE JANEIRO", "BRASIL"),
    "SANTIAGO DE CHILE": ("SANTIAGO", "CHILE"),
    "SANTIAGO DE CHILE CHILE": ("SANTIAGO", "CHILE"),
    "BARCELONA ESPANA": ("BARCELONA", "ESPANA"),
    "SAN PABLO BRASIL": ("SAN PABLO", "BRASIL"),
    "LA PAZ BOLIVIA": ("LA PAZ", "BOLIVIA"),
    "ORURO BOLIVIA": ("ORURO", "BOLIVIA"),
    "ANTOFAGASTA CHILE": ("ANTOFAGASTA", "CHILE"),
    "PARIS FRANCIA": ("PARIS", "FRANCIA"),
    "MADRID ESPANA": ("MADRID", "ESPANA"),
    "KALLITHEA ATTICA GRECIA": ("KALLITHEA ATTICA", "GRECIA"),
    "MARRAKECH MARRUECOS": ("MARRAKECH", "MARRUECOS"),
    "SAN ESTEBAN DE LA SIERRA SALAMANCA ESPANA": ("SAN ESTEBAN DE LA SIERRA", "ESPANA"),
    "WOLIN POMERANIA POLONIA": ("WOLIN POMERANIA", "POLONIA"),
    "ZURICH SUIZA": ("ZURICH", "SUIZA"),
    "ASUNCION PARAGUAY SDH": ("ASUNCION", "PARAGUAY"),
    "SAN PABLO BRASIL": ("SAN PABLO", "BRASIL"),
}


def normalize_place_text(value: str) -> str:
    text = strip_accents(value.upper())
    text = re.sub(r"[^A-Z0-9\s]", " ", text)
    text = norm_space(text)
    return text


def normalize_place_identity(value: str) -> str:
    text = value
    if "FRANCIA" not in text:
        text = re.sub(r"\bBOULOGNE\b(?!\s+SUR\s+MER)", "BOULOGNE SUR MER", text)
    text = re.sub(r"\bCAPITAL\s+FFDERAL\b", "CAPITAL FEDERAL", text)
    text = re.sub(r"\bCDAD\b", "CIUDAD", text)
    text = re.sub(r"\bCAP\s+FED\b", "CAPITAL FEDERAL", text)
    text = re.sub(r"\bSTA\b", "SANTA", text)
    text = re.sub(r"\bSECUETRADO\b", "SECUESTRADO", text)
    text = re.sub(r"\bSECUESTRAD[OA]S?\b", "SECUESTRADO", text)
    text = re.sub(r"\bFUE\s+SECUESTRADO\b", "SECUESTRADO", text)
    text = re.sub(r"^SU\s+DOMICILIO\s+UBICADO\s+EN\s+", "", text)
    text = re.sub(r"^SU\s+DOMICILIO\s+", "", text)
    text = re.sub(r"^EN\s+SU\s+DOMICILIO\s+", "", text)
    text = re.sub(r"\bDE\s+SU\s+DOMICILIO\b", "", text)
    text = re.sub(r"\bEN\s+SU\s+DOMICILIO\b", "", text)
    text = re.sub(r"\bVIA\s+PUBLICA\b", "", text)
    text = re.sub(r"\bDOMICILIO\s+PARTICULAR\b", "", text)
    text = re.sub(r"\bSECUESTRADO\b", "", text)
    text = re.sub(r"\bASESINAD[OA]S?\b", "", text)
    text = re.sub(r"\bNO\s+CONSTA\b", "", text)
    text = re.sub(r"\bSE\s+DESCONOCE\b", "", text)
    text = re.sub(r"\bSIN\s+DETERMINAR\b", "", text)
    text = re.sub(r"^\(?\s*O\s+\d{1,2}[\s/\-]\d{1,2}[\s/\-]\d{2,4}\s*\)?", "", text)
    text = re.sub(r"\b\(?\s*SDH\s+NO\s+CONSTA\s*\)?", "", text)
    text = re.sub(r"\b\(?\s*SDH\s*\)?", "", text)
    text = re.sub(r"\bASESINAD[OA]\s+\d{1,2}[\-/]\d{1,2}[\-/]\d{2,4}\b", "", text)
    text = re.sub(r"\bSEC\s+EN\s+CAP\s+FED\s+EL\s+\d{1,2}[\-/]\d{1,2}[\-/]\d{2,4}\b", "", text)
    # Keep canonical head and drop frequent descriptive tails.
    text = re.sub(r"\bSU\s+DOMICILIO\b.*$", "", text)
    text = re.sub(r"\bVIVIENDA\s+DE\b.*$", "", text)
    text = re.sub(r"\bVIVIENDA\s+PARTICULAR\b.*$", "", text)
    text = re.sub(r"\bCASA\s+DE\b.*$", "", text)
    text = re.sub(r"\bLUGAR\s+DE\s+TRABAJO\b.*$", "", text)
    text = re.sub(r"\bINMEDIACIONES\s+DE\b.*$", "", text)
    # For strings like "CASTELAR BS AS ...", keep locality + provincial clue.
    text = re.sub(r"^([A-Z\s]{3,}?)\s+BS\s+AS\b.*$", r"\1 BS AS", text)
    text = re.sub(r"\bEN\s+LA\b$", "", text)
    text = re.sub(r"\bEN\s+EL\b$", "", text)
    return norm_space(text)


def extract_specific_address(raw: Optional[str]) -> Optional[Dict[str, Any]]:
    text = clean_text(raw)
    if text is None:
        return None

    upper = strip_accents(text.upper())
    # Drop contextual parenthesis usually containing locality notes.
    upper = re.sub(r"\([^)]*\)", " ", upper)
    upper = re.sub(r"[^A-Z0-9\s,\-\./]", " ", upper)
    upper = norm_space(upper)

    # Remove frequent narrative prefixes before extracting the street segment.
    prefix_patterns = (
        r"^SECUESTRAD[OA]\s+",
        r"^FUE\s+SECUESTRAD[OA]\s+",
        r"^EN\s+LAS\s+CERCANIAS\s+DE\s+",
        r"^EN\s+LA\s+VIA\s+PUBLICA\s+",
        r"^DE\s+SU\s+",
        r"^SU\s+",
        r"^LUGAR\s+DE\s+TRABAJO\s+",
    )
    candidate = upper
    for pattern in prefix_patterns:
        candidate = re.sub(pattern, "", candidate)
    candidate = norm_space(candidate)

    # Institutional locations (e.g. COMISARIA 1 DE SAN MARTIN) are not street addresses.
    if re.match(r"^(COMISARIA|SUBCOMISARIA|REGIMIENTO|UNIDAD PENAL|ALCAIDIA|DESTACAMENTO)\b", candidate):
        return None

    narrative_starts = (
        r"^ASESINAD[OA]\s+\d{1,2}[\-/]\d{1,2}[\-/]\d{2,4}",
        r"^SEC\s+EN\s+CAP\s+FED\s+EL\s+\d{1,2}[\-/]\d{1,2}[\-/]\d{2,4}",
        r"^SEGUN\s+DENUNCIA",
        r"^SE\s+DESCONOCE",
        r"^SIN\s+DETERMINAR",
        r"^NO\s+CONSTA",
    )
    if any(re.search(p, candidate) for p in narrative_starts):
        return None

    # If a long narrative includes a street+number fragment, keep only that fragment.
    long_with_fragment = re.search(
        r"\b([A-Z]{3,}(?:\s+[A-Z]{2,}){0,5}\s+\d{1,5}(?:\s*(?:DTO|DEPTO|PISO|N)\s*[A-Z0-9\"']{1,6})?)\b",
        candidate,
    )
    if long_with_fragment and len(candidate) > 35:
        candidate = norm_space(long_with_fragment.group(1))

    chunks = [norm_space(c) for c in re.split(r"[,;-]", candidate) if norm_space(c)]
    if not chunks:
        return None

    generic_chunks = {
        "SU DOMICILIO",
        "SU LUGAR DE TRABAJO",
        "SE DESCONOCE",
        "SIN DETERMINAR",
        "NO CONSTA",
        "VIA PUBLICA",
    }
    chosen = None
    for chunk in chunks:
        if chunk in generic_chunks:
            continue
        has_number = re.search(r"\b\d{1,5}\b", chunk) is not None
        has_corner = re.search(r"\b[A-Z]{2,}\s+Y\s+[A-Z]{2,}\b", chunk) is not None and len(chunk.split()) <= 8
        if has_number or has_corner:
            chosen = chunk
            break
    if chosen is None:
        return None

    via_match = re.match(r"^(AV(?:ENIDA)?|CALLE|PJE|PASAJE|RUTA|DIAGONAL|BLVD|BOULEVARD)\s+(.+)$", chosen)
    via = None
    numero = None
    if via_match:
        via = via_match.group(1)
    num_match = re.search(r"\b(\d{1,5})\b", chosen)
    if num_match:
        numero = num_match.group(1)

    if via and numero:
        confianza = 0.95
    elif numero:
        confianza = 0.85
    else:
        confianza = 0.65

    direccion_norm = norm_space(chosen)
    if len(direccion_norm) < 5:
        return None

    return {
        "direccion_raw": text,
        "direccion_norm": direccion_norm,
        "via": via,
        "numero": numero,
        "piso_depto": None,
        "confianza_parseo": confianza,
    }


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

    country_key = "lugar:PAIS:argentina"

    if match.level == "PROVINCIA":
        lugar_key = make_lugar_key("PROVINCIA", match.name, country_key)
        return {
            "alias_norm": alias_norm,
            "tipo": "PROVINCIA",
            "nombre_canonico": match.name,
            "lugar_key": lugar_key,
            "parent_key": country_key,
            "hierarchy_keys": [lugar_key, country_key],
        }

    province_key = make_lugar_key("PROVINCIA", match.provincia_name, country_key)
    city_like = "CIUDAD" if match.level in {"LOCALIDAD", "MUNICIPIO"} else "DEPARTAMENTO"
    if match.level in {"LOCALIDAD", "MUNICIPIO"} and match.departamento_name:
        department_key = make_lugar_key("DEPARTAMENTO", match.departamento_name, province_key)
        lugar_key = make_lugar_key(city_like, match.name, department_key)
        hierarchy_keys = [lugar_key, department_key, province_key, country_key]
        parent_key = department_key
    elif match.level == "DEPARTAMENTO":
        lugar_key = make_lugar_key("DEPARTAMENTO", match.name, province_key)
        hierarchy_keys = [lugar_key, province_key, country_key]
        parent_key = province_key
    else:
        lugar_key = make_lugar_key(city_like, match.name, province_key)
        hierarchy_keys = [lugar_key, province_key, country_key]
        parent_key = province_key

    return {
        "alias_norm": alias_norm,
        "tipo": city_like,
        "nombre_canonico": match.name,
        "lugar_key": lugar_key,
        "parent_key": parent_key,
        "hierarchy_keys": hierarchy_keys,
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


def _has_caba_context_hint(alias_norm: str) -> bool:
    hints = (
        "CAPITAL FEDERAL",
        "CAP FED",
        "CABA",
        "CIUDAD DE BS AS",
        "CIUDAD DE BUENOS AIRES",
        "CIUDAD AUTONOMA DE BUENOS AIRES",
    )
    padded = f" {alias_norm} "
    return any(h in padded for h in hints)


def _strip_caba_context(alias_norm: str) -> str:
    text = f" {alias_norm} "
    for pat in (
        r"\bCAPITAL\s+FEDERAL\b",
        r"\bCAP\s+FED\b",
        r"\bCABA\b",
        r"\bCIUDAD\s+DE\s+BS\s+AS\b",
        r"\bCIUDAD\s+DE\s+BUENOS\s+AIRES\b",
        r"\bCIUDAD\s+AUTONOMA\s+DE\s+BUENOS\s+AIRES\b",
    ):
        text = re.sub(pat, " ", text)
    text = re.sub(r"\b(CIUDAD|CDAD)\b", " ", text)
    text = re.sub(r"\b(DE|DEL|EN|LA|EL)\b", " ", text)
    return norm_space(text)


def _resolve_caba_contextual(alias_norm: str, resolver: Optional[PlaceGazetteer], min_score: float, ambiguity_delta: float) -> Dict[str, Any]:
    # Default to CABA when the text explicitly references Capital Federal/CABA.
    caba = _resolve_caba(alias_norm)
    if resolver is None:
        return caba if caba is not None else {}

    stripped = _strip_caba_context(alias_norm)
    if stripped and re.search(r"\d", stripped) is None and len(stripped.split()) <= 5:
        georef = _resolve_with_georef(stripped, resolver, min_score=min_score, ambiguity_delta=ambiguity_delta)
        if georef is not None and georef.get("tipo") == "CIUDAD":
            parent_key = georef.get("parent_key") or ""
            if "ciudad_autonoma_de_buenos_aires" in parent_key:
                georef["alias_norm"] = alias_norm
                return georef
    return caba if caba is not None else {}


def _resolve_foreign_place(alias_norm: str) -> Optional[Dict[str, Any]]:
    domestic_hints = ("CAPITAL FEDERAL", "BS AS", "BUENOS AIRES", "CABA")
    if any(h in alias_norm for h in domestic_hints):
        return None

    if alias_norm in FOREIGN_COUNTRY_EQUIV:
        country_name, country_code = FOREIGN_COUNTRY_EQUIV[alias_norm]
        country_key = make_lugar_key("PAIS", country_name, None)
        return {
            "alias_norm": alias_norm,
            "tipo": "PAIS",
            "nombre_canonico": country_name,
            "lugar_key": country_key,
            "parent_key": None,
            "hierarchy_keys": [country_key],
            "pais_code": country_code,
        }

    alias_clean = re.sub(r"\bSDH\b", "", alias_norm)
    alias_clean = re.sub(r"\bNO\s+CONSTA\b", "", alias_clean)
    alias_clean = norm_space(alias_clean)

    mapped = FOREIGN_CITY_COUNTRY_EQUIV.get(alias_clean)
    if mapped is None:
        for country_alias, (country_name, _country_code) in FOREIGN_COUNTRY_EQUIV.items():
            if alias_clean.endswith(f" {country_alias}") and len(alias_clean.split()) <= 7:
                city_name = alias_clean[: -len(country_alias)].strip()
                if city_name and city_name != "DE":
                    mapped = (city_name, country_name)
                    break

    if mapped is None:
        return None

    city_name, country_name = mapped
    _country_norm, country_code = FOREIGN_COUNTRY_EQUIV.get(country_name, (country_name, "XX"))
    country_key = make_lugar_key("PAIS", country_name, None)
    city_key = make_lugar_key("CIUDAD", city_name, country_key)
    return {
        "alias_norm": alias_norm,
        "tipo": "CIUDAD",
        "nombre_canonico": city_name,
        "lugar_key": city_key,
        "parent_key": country_key,
        "hierarchy_keys": [city_key, country_key],
        "pais_code": country_code,
    }


def _has_explicit_province_hint(alias_norm: str) -> bool:
    province_hints = set(PROVINCE_ABBR.keys()) | {"CAPITAL FEDERAL", "CABA", "CIUDAD AUTONOMA DE BUENOS AIRES"}
    padded = f" {alias_norm} "
    return any(f" {hint} " in padded for hint in province_hints)


def _is_pure_address_like(alias_norm: str) -> bool:
    if re.search(r"\b\d{1,5}\b", alias_norm) is None:
        return False
    return re.match(r"^(AV(?:ENIDA)?|CALLE|PJE|PASAJE|RUTA|DIAGONAL|BLVD|BOULEVARD)\b", alias_norm) is not None


def _can_assume_buenos_aires(alias_norm: str) -> bool:
    if _has_explicit_province_hint(alias_norm):
        return False
    if re.search(r"\d", alias_norm):
        return False
    if len(alias_norm.split()) > 5:
        return False
    blocked_tokens = {
        "CAMARA",
        "REGIMIENTO",
        "DESCAMPADO",
        "TRAYECTO",
        "SE",
        "DESCONOCE",
        "SIN",
        "DETERMINAR",
        "DOMICILIO",
    }
    if any(t in blocked_tokens for t in alias_norm.split()):
        return False
    return True


def _preferred_province_from_alias(alias_norm: str) -> str:
    padded = f" {alias_norm} "
    for hint, prov in sorted(PROVINCE_ABBR.items(), key=lambda kv: len(kv[0]), reverse=True):
        if f" {hint} " in padded:
            return prov
    return "BUENOS AIRES"


def _strip_trailing_province_hint(alias_norm: str) -> str:
    text = norm_space(alias_norm)
    for hint in sorted(PROVINCE_ABBR.keys(), key=len, reverse=True):
        if text.endswith(f" {hint}"):
            return norm_space(text[: -len(hint)])
    return text


def _canonicalize_admin_context_name(context_name: str, preferred_province: str) -> str:
    context = norm_space(context_name)
    if preferred_province == "BUENOS AIRES":
        if context == "SAN MARTIN":
            return "GENERAL SAN MARTIN"
        if context == "GRAL SAN MARTIN":
            return "GENERAL SAN MARTIN"
    return context


def _resolve_segmented_place(alias_norm: str, resolver: PlaceGazetteer) -> Optional[Dict[str, Any]]:
    base_alias = _strip_trailing_province_hint(alias_norm)
    tokens = [t for t in base_alias.split() if t]
    if len(tokens) < 2 or len(tokens) > 5:
        return None
    if re.search(r"\d", alias_norm):
        return None
    if any(country in base_alias for country in FOREIGN_COUNTRY_EQUIV.keys()):
        return None

    has_explicit_province = _has_explicit_province_hint(alias_norm)
    preferred_province = _preferred_province_from_alias(alias_norm)
    max_ctx_len = min(3, len(tokens) - 1)
    for ctx_len in range(1, max_ctx_len + 1):
        city_name = norm_space(" ".join(tokens[:-ctx_len]))
        context_name = norm_space(" ".join(tokens[-ctx_len:]))
        context_name = _canonicalize_admin_context_name(context_name, preferred_province)
        if not city_name or not context_name:
            continue
        if _is_pure_address_like(city_name):
            continue

        admin = resolver.resolve_admin_context(context_name, preferred_province_name=preferred_province)
        # If no province is stated, keep the BA default strict and avoid drifting
        # to similarly named contexts in other provinces.
        if not has_explicit_province and admin is not None and admin.provincia_name != "BUENOS AIRES":
            admin = None
        if admin is None:
            continue

        country_key = "lugar:PAIS:argentina"
        province_name = "BUENOS AIRES" if not has_explicit_province else admin.provincia_name
        province_key = make_lugar_key("PROVINCIA", province_name, country_key)
        if admin.level in {"MUNICIPIO", "DEPARTAMENTO"}:
            admin_parent_name = admin.departamento_name or admin.name
            parent_key = make_lugar_key("DEPARTAMENTO", admin_parent_name, province_key)
            hierarchy_keys = [
                make_lugar_key("CIUDAD", city_name, parent_key),
                parent_key,
                province_key,
                country_key,
            ]
        elif admin.level == "PROVINCIA":
            parent_key = province_key
            hierarchy_keys = [make_lugar_key("CIUDAD", city_name, parent_key), parent_key, country_key]
        else:
            parent_key = province_key
            hierarchy_keys = [make_lugar_key("CIUDAD", city_name, parent_key), parent_key, country_key]

        return {
            "alias_norm": alias_norm,
            "tipo": "CIUDAD",
            "nombre_canonico": city_name,
            "lugar_key": hierarchy_keys[0],
            "parent_key": parent_key,
            "hierarchy_keys": hierarchy_keys,
        }

    return None


def _extract_toponym_from_institution(alias_norm: str) -> Optional[str]:
    m = re.match(
        r"^(COMISARIA|SUBCOMISARIA|REGIMIENTO|UNIDAD PENAL|ALCAIDIA|DESTACAMENTO)\s*(\d{1,4})?\s*(?:DE|DEL|EN)\s+(.+)$",
        alias_norm,
    )
    if not m:
        return None
    tail = norm_space(m.group(3) or "")
    if not tail:
        return None
    return norm_space(tail)


def _extract_repeated_trailing_toponym(alias_norm: str) -> str:
    base_alias = _strip_trailing_province_hint(alias_norm)
    tokens = [t for t in base_alias.split() if t]
    if len(tokens) < 4:
        return alias_norm

    last = tokens[-1]
    prev = tokens[-2]
    if last != prev or len(last) < 4:
        return alias_norm

    noise_tokens = {
        "EN",
        "LA",
        "EL",
        "DE",
        "DEL",
        "AL",
        "Y",
        "E",
        "LAS",
        "LOS",
    }
    has_noise_prefix = any(tok in noise_tokens for tok in tokens[:-2])
    if len(tokens) >= 7 or has_noise_prefix:
        return last

    return alias_norm


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

    # For records like "SE DESCONOCE (Cafe X y Y)", keep parenthesis content as fallback.
    paren = re.findall(r"\(([^)]{4,})\)", text)
    fallback_paren = clean_text(paren[-1]) if paren else None

    alias_norm = normalize_place_identity(normalize_place_text(text))
    if not alias_norm and fallback_paren:
        alias_norm = normalize_place_identity(normalize_place_text(fallback_paren))
    if not alias_norm or alias_norm in UNKNOWN_PLACE_VALUES:
        return None

    institution_toponym = _extract_toponym_from_institution(alias_norm)
    if institution_toponym:
        alias_norm = institution_toponym

    alias_norm = _extract_repeated_trailing_toponym(alias_norm)

    if alias_norm in {"SU", "DE SU", "DE LA"}:
        return None

    if _is_pure_address_like(alias_norm):
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

    resolver: Optional[PlaceGazetteer] = None
    if use_georef:
        resolver = _load_georef_resolver(str(georef_catalog_path))

    if _has_caba_context_hint(alias_norm):
        caba_context = _resolve_caba_contextual(alias_norm, resolver, georef_min_score, georef_ambiguity_delta)
        if caba_context:
            caba_context["alias_raw"] = text
            return caba_context

    foreign_resolved = _resolve_foreign_place(alias_norm)
    if foreign_resolved is not None:
        foreign_resolved["alias_raw"] = text
        return foreign_resolved

    if use_georef:
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
            segmented = _resolve_segmented_place(alias_norm, resolver)
            if segmented is not None:
                segmented["alias_raw"] = text
                return segmented

    caba_resolved = _resolve_caba(alias_norm)
    if caba_resolved is not None:
        caba_resolved["alias_raw"] = text
        return caba_resolved

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

    if _can_assume_buenos_aires(alias_norm):
        parent_key = make_lugar_key("PROVINCIA", "BUENOS AIRES", "lugar:PAIS:argentina")
        lugar_key = make_lugar_key("CIUDAD", alias_norm, parent_key)
        return {
            "alias_raw": text,
            "alias_norm": alias_norm,
            "tipo": "CIUDAD",
            "nombre_canonico": alias_norm,
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
