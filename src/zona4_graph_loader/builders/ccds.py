from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from zona4_graph_loader.constants import GEOREF_AMBIGUITY_DELTA, GEOREF_CATALOG_PATH, GEOREF_MIN_SCORE
from zona4_graph_loader.domain.date_norm import parse_partial_ymd
from zona4_graph_loader.domain.place_norm import resolve_place
from zona4_graph_loader.domain.text_norm import clean_text, slugify_name


def _to_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _ccd_rel_to_tipo(relacion: str) -> str:
    rel = (relacion or "").strip().lower()
    if rel == "pario_en":
        return "PARIO_EN"
    return "PRESENTE_EN"


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
) -> Optional[str]:
    # Use existing resolved keys as fallback checks for geographic containment
    candidates: List[str] = []
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


def _parse_ccd_fecha(fecha_values: List[str]) -> Optional[str]:
    if not fecha_values:
        return None

    cleaned = [f.strip() for f in fecha_values if isinstance(f, str) and f.strip()]
    if not cleaned:
        return None

    parsed = [parse_partial_ymd(v) for v in cleaned]
    valid = [p for p in parsed if p[0] is not None]
    if not valid:
        return " | ".join(cleaned)

    # Return chronological start date
    starts = sorted(v[0] for v in valid if v[0] is not None)
    return starts[0] if starts else None


def build_ccd_rows(
    detalles_data: List[Dict[str, Any]],
    ccd_catalog: List[Dict[str, Any]],
    *,
    existing_lugar_keys: Optional[set[str]] = None,
    use_georef: bool = True,
    georef_catalog_path: Path = GEOREF_CATALOG_PATH,
    georef_min_score: float = GEOREF_MIN_SCORE,
    georef_ambiguity_delta: float = GEOREF_AMBIGUITY_DELTA,
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
    direcciones: Dict[str, Dict[str, Any]] = {}
    direccion_lugar_links: List[Dict[str, Any]] = []
    persona_lugar_links: List[Dict[str, Any]] = []

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

            # Register Clandestine Detention Center (CCD) as Lugar with tipoGeopolitico "CCD"
            lugares[lugar_key] = {
                "lugar_key": lugar_key,
                "nombre": denominacion.upper(),
                "tipoGeopolitico": "CCD",
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

            # Map the exact coordinates/address as DirecciónCCD
            direccion_ccd_key = f"direccion_ccd:ccd:{id_ccd}"
            coordenadas_str = f"{lat},{lon}" if lat is not None and lon is not None else "DESCONOCIDAS"
            direcciones[direccion_ccd_key] = {
                "direccion_ccd_key": direccion_ccd_key,
                "coordenadas": coordenadas_str,
                "direccionExacta": ubicacion or denominacion,
                "lugar_key": lugar_key,
            }
            direccion_lugar_links.append({
                "direccion_ccd_key": direccion_ccd_key,
                "lugar_key": lugar_key,
            })

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
            )
            if resolved_lugar_key and resolved_lugar_key != lugar_key:
                parents.add((lugar_key, resolved_lugar_key))

            fecha_raw = ref.get("fecha")
            fecha_values = fecha_raw if isinstance(fecha_raw, list) else []
            fecha_iso = _parse_ccd_fecha(fecha_values)
            relacion = clean_text(ref.get("relacion")) or "desconocida"

            persona_lugar_links.append({
                "persona_key": f"registro:{registro}",
                "lugar_key": lugar_key,
                "tipo_relacion": _ccd_rel_to_tipo(relacion),
                "fecha": fecha_iso or "DESCONOCIDA",
                "origen": "ccds_json",
            })

    return {
        "lugares": list(lugares.values()),
        "direcciones": list(direcciones.values()),
        "direccion_lugar_links": direccion_lugar_links,
        "parents": [{"child_key": child, "parent_key": parent} for child, parent in sorted(parents)],
        "persona_lugar_links": persona_lugar_links,
    }
