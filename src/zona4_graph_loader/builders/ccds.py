from __future__ import annotations

import json
import urllib.parse
import urllib.request
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from zona4_graph_loader.constants import GEOREF_AMBIGUITY_DELTA, GEOREF_CATALOG_PATH, GEOREF_MIN_SCORE
from zona4_graph_loader.domain.date_norm import parse_partial_ymd
from zona4_graph_loader.domain.place_norm import resolve_place
from zona4_graph_loader.domain.text_norm import clean_text, slugify_name

GEOREF_API_ROOT = "https://apis.datos.gob.ar/georef/api"


def _to_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _ccd_rel_to_tipo(relacion: str) -> str:
    rel = (relacion or "").strip().lower()
    if rel == "secuestrada_en":
        return "SECUESTRO_CCD"
    if rel == "pario_en":
        return "PARTO_CAUTIVERIO_CCD"
    return "EVENTO_CCD"


def _ccd_rel_to_rol(relacion: str) -> str:
    rel = (relacion or "").strip().lower()
    if rel == "secuestrada_en":
        return "victima"
    if rel == "pario_en":
        return "persona_que_pario"
    return "persona_mencionada_ccd"


@lru_cache(maxsize=256)
def _reverse_georef_ubicacion(lat_str: str, lon_str: str, timeout: int) -> Optional[Dict[str, Any]]:
    params = urllib.parse.urlencode(
        {
            "lat": lat_str,
            "lon": lon_str,
        }
    )
    url = f"{GEOREF_API_ROOT}/ubicacion?{params}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None

    ubicacion = payload.get("ubicacion")
    if isinstance(ubicacion, dict):
        return ubicacion
    return None


def _coord_to_place_hint(lat: Optional[float], lon: Optional[float], timeout: int) -> Optional[str]:
    if lat is None or lon is None:
        return None

    ubicacion = _reverse_georef_ubicacion(f"{lat:.6f}", f"{lon:.6f}", timeout)
    if not ubicacion:
        return None

    provincia = clean_text((ubicacion.get("provincia") or {}).get("nombre"))
    municipio = clean_text((ubicacion.get("municipio") or {}).get("nombre"))
    departamento = clean_text((ubicacion.get("departamento") or {}).get("nombre"))

    principal = municipio or departamento
    if not principal:
        return provincia
    if provincia:
        return f"{principal}, {provincia}"
    return principal


def _resolve_existing_lugar_key(
    *,
    lat: Optional[float],
    lon: Optional[float],
    ubicacion_text: Optional[str],
    denominacion_text: Optional[str],
    existing_lugar_keys: set[str],
    use_georef: bool,
    georef_catalog_path: Path,
    georef_min_score: float,
    georef_ambiguity_delta: float,
    georef_api_timeout: int,
) -> Optional[str]:
    hint = _coord_to_place_hint(lat, lon, georef_api_timeout)
    candidates: List[str] = []
    if hint:
        candidates.append(hint)
    if ubicacion_text:
        candidates.append(ubicacion_text)
    if denominacion_text:
        candidates.append(denominacion_text)

    if not candidates:
        return None

    for candidate in candidates:
        resolved = resolve_place(
            candidate,
            use_georef=use_georef,
            georef_catalog_path=georef_catalog_path,
            georef_min_score=georef_min_score,
            georef_ambiguity_delta=georef_ambiguity_delta,
        )
        if not resolved:
            continue

        lugar_key = resolved.get("lugar_key")
        if isinstance(lugar_key, str) and lugar_key in existing_lugar_keys and resolved.get("tipo") != "INDETERMINADO":
            return lugar_key

        parent_key = resolved.get("parent_key")
        if isinstance(parent_key, str) and parent_key in existing_lugar_keys:
            return parent_key

    return None


def _parse_ccd_fecha(fecha_values: List[str]) -> Dict[str, Optional[str]]:
    if not fecha_values:
        return {
            "fecha": None,
            "fecha_inicio": None,
            "fecha_fin": None,
            "fecha_precision": None,
            "fecha_raw": None,
        }

    cleaned = [f.strip() for f in fecha_values if isinstance(f, str) and f.strip()]
    if not cleaned:
        return {
            "fecha": None,
            "fecha_inicio": None,
            "fecha_fin": None,
            "fecha_precision": None,
            "fecha_raw": None,
        }

    parsed = [parse_partial_ymd(v) for v in cleaned]
    valid = [p for p in parsed if p[0] is not None and p[1] is not None]
    if not valid:
        return {
            "fecha": None,
            "fecha_inicio": None,
            "fecha_fin": None,
            "fecha_precision": None,
            "fecha_raw": " | ".join(cleaned),
        }

    if len(valid) == 1:
        start, end, precision = valid[0]
        return {
            "fecha": start,
            "fecha_inicio": start,
            "fecha_fin": end,
            "fecha_precision": precision,
            "fecha_raw": " | ".join(cleaned),
        }

    starts = sorted(v[0] for v in valid if v[0] is not None)
    ends = sorted(v[1] for v in valid if v[1] is not None)
    return {
        "fecha": starts[0] if starts else None,
        "fecha_inicio": starts[0] if starts else None,
        "fecha_fin": ends[-1] if ends else None,
        "fecha_precision": "RANGE",
        "fecha_raw": " | ".join(cleaned),
    }


def build_ccd_rows(
    detalles_data: List[Dict[str, Any]],
    ccd_catalog: List[Dict[str, Any]],
    *,
    existing_lugar_keys: Optional[set[str]] = None,
    use_georef: bool = True,
    georef_catalog_path: Path = GEOREF_CATALOG_PATH,
    georef_min_score: float = GEOREF_MIN_SCORE,
    georef_ambiguity_delta: float = GEOREF_AMBIGUITY_DELTA,
    georef_api_timeout: int = 8,
) -> Dict[str, List[Dict[str, Any]]]:
    existing_lugar_keys = existing_lugar_keys or set()

    ccd_by_id: Dict[str, Dict[str, Any]] = {}
    for ccd in ccd_catalog:
        id_ccd = clean_text(ccd.get("id_ccd"))
        if not id_ccd:
            continue
        ccd_by_id[id_ccd] = ccd

    lugares: Dict[str, Dict[str, Any]] = {}
    parents: set[tuple[str, str]] = set()
    eventos: List[Dict[str, Any]] = []
    evento_links: List[Dict[str, Any]] = []
    evento_ccd_links: List[Dict[str, Any]] = []

    for item in detalles_data:
        registro = item.get("registro")
        if registro is None:
            continue

        ccd_refs = item.get("ccds")
        if not isinstance(ccd_refs, list):
            continue

        for idx, ref in enumerate(ccd_refs):
            if not isinstance(ref, dict):
                continue

            id_ccd = clean_text(ref.get("id_ccd"))
            if not id_ccd:
                continue

            ccd = ccd_by_id.get(id_ccd)
            if not ccd:
                continue

            denominacion = clean_text(ccd.get("denominacion")) or f"CCD {id_ccd}"
            ubicacion = clean_text(ccd.get("ubicacion"))
            lugar_key = f"lugar:CCD:{slugify_name(id_ccd)}"
            lat = _to_float(ccd.get("lat"))
            lon = _to_float(ccd.get("lon"))

            lugares[lugar_key] = {
                "lugar_key": lugar_key,
                "nombre_canonico": denominacion.upper(),
                "tipo": "CCD",
                "pais_code": "AR",
                "fuente": "ccds_json",
                "lat": lat,
                "lon": lon,
                "id_ccd": id_ccd,
                "zona": clean_text(ccd.get("zona")),
                "subzona": clean_text(ccd.get("subzona")),
                "area": clean_text(ccd.get("area")),
                "jurisdiccion": clean_text(ccd.get("jurisdiccion")),
                "ubicacion": ubicacion,
                "emplazamiento_propiedad": clean_text(ccd.get("emplazamiento_propiedad")),
            }

            resolved_lugar_key = _resolve_existing_lugar_key(
                lat=lat,
                lon=lon,
                ubicacion_text=ubicacion,
                denominacion_text=denominacion,
                existing_lugar_keys=existing_lugar_keys,
                use_georef=use_georef,
                georef_catalog_path=georef_catalog_path,
                georef_min_score=georef_min_score,
                georef_ambiguity_delta=georef_ambiguity_delta,
                georef_api_timeout=georef_api_timeout,
            )
            if resolved_lugar_key and resolved_lugar_key != lugar_key:
                parents.add((lugar_key, resolved_lugar_key))

            fecha_raw = ref.get("fecha")
            fecha_values = fecha_raw if isinstance(fecha_raw, list) else []
            fecha_data = _parse_ccd_fecha(fecha_values)
            relacion = clean_text(ref.get("relacion")) or "desconocida"
            certeza = clean_text(ref.get("certeza"))
            evento_key = f"evento:detalles:ccd:{registro}:{id_ccd}:{idx}"

            eventos.append(
                {
                    "evento_key": evento_key,
                    "tipo": _ccd_rel_to_tipo(relacion),
                    "fecha": fecha_data["fecha"],
                    "fecha_inicio": fecha_data["fecha_inicio"],
                    "fecha_fin": fecha_data["fecha_fin"],
                    "fecha_precision": fecha_data["fecha_precision"],
                    "lugar": ubicacion,
                    "descripcion_raw": fecha_data["fecha_raw"],
                    "fuente": "parque_ccds",
                    "persona_key": f"registro:{registro}",
                    "rol": _ccd_rel_to_rol(relacion),
                    "id_ccd": id_ccd,
                    "ccd_relacion": relacion,
                    "ccd_certeza": certeza,
                    "ccd_denominacion": denominacion,
                }
            )

            evento_ccd_links.append(
                {
                    "evento_key": evento_key,
                    "ccd_lugar_key": lugar_key,
                    "fuente": "parque_ccds",
                    "ccd_relacion": relacion,
                    "ccd_certeza": certeza,
                }
            )

            evento_links.append(
                {
                    "evento_key": evento_key,
                    "lugar_key": resolved_lugar_key or lugar_key,
                    "fuente": "parque_ccds",
                    "campo_fuente": "ccds.id_ccd",
                    "alias_raw": denominacion,
                }
            )

    return {
        "eventos": eventos,
        "lugares": list(lugares.values()),
        "parents": [{"child_key": child, "parent_key": parent} for child, parent in sorted(parents)],
        "evento_links": evento_links,
        "evento_ccd_links": evento_ccd_links,
    }
