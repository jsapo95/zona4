from __future__ import annotations

import difflib
import hashlib
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List

from zona4_graph_loader.builders.base import CanonicalDataset
from zona4_graph_loader.constants import ALIAS_ROOT_PARENT_KEY, DIRECTIONAL_TOKENS
from zona4_graph_loader.domain.date_norm import parse_ddmmyyyy
from zona4_graph_loader.domain.place_norm import extract_specific_address, resolve_place
from zona4_graph_loader.domain.text_norm import clean_text, slugify_name


def _node_from_lugar_key(lugar_key: str) -> Dict[str, str]:
    core = lugar_key.split("|", 1)[0]
    parts = core.split(":", 2)
    if len(parts) != 3:
        return {
            "lugar_key": lugar_key,
            "nombre": core.upper(),
            "tipoGeopolitico": "INDETERMINADO",
        }

    tipo = parts[1].upper()
    nombre = parts[2].replace("_", " ").upper()
    return {
        "lugar_key": lugar_key,
        "nombre": nombre,
        "tipoGeopolitico": tipo,
    }


def build_lugar_layer_rows(
    data: List[Dict[str, Any]],
    *,
    use_georef: bool = True,
    georef_catalog_path: Path,
    georef_min_score: float,
    georef_ambiguity_delta: float,
) -> CanonicalDataset:
    pais_key = "lugar:PAIS:argentina"
    lugares: Dict[str, Dict[str, Any]] = {
        pais_key: {
            "lugar_key": pais_key,
            "nombre": "ARGENTINA",
            "tipoGeopolitico": "PAIS",
            "pais_code": "AR",
            "fuente": "normalizacion_lugar",
            "tipo_entidad": "Lugar",
        }
    }
    parents: set[tuple[str, str]] = set()
    aliases: Dict[str, Dict[str, Any]] = {}
    direcciones: Dict[str, Dict[str, Any]] = {}
    direccion_lugar_links: list[Dict[str, Any]] = []
    persona_lugar_links: list[Dict[str, Any]] = []

    def ensure_lugar_node(lugar_key: str) -> None:
        if lugar_key in lugares:
            return
        node = _node_from_lugar_key(lugar_key)
        pais_code = "AR"
        if node["tipoGeopolitico"] == "PAIS" and node["nombre"] != "ARGENTINA":
            pais_code = "XX"
        lugares[lugar_key] = {
            "lugar_key": node["lugar_key"],
            "nombre": node["nombre"],
            "tipoGeopolitico": node["tipoGeopolitico"],
            "pais_code": pais_code,
            "fuente": "normalizacion_lugar",
            "tipo_entidad": "Lugar",
        }

    def register_place(
        place: Dict[str, Any],
        field: str,
        registro: int,
        persona_campo: str | None,
        fecha_event: str | None
    ) -> None:
        lugares[place["lugar_key"]] = {
            "lugar_key": place["lugar_key"],
            "nombre": place["nombre_canonico"],
            "tipoGeopolitico": place["tipo"],
            "pais_code": place.get("pais_code") or "AR",
            "fuente": "normalizacion_lugar",
            "tipo_entidad": "Lugar",
        }
        hierarchy_keys = place.get("hierarchy_keys")
        if isinstance(hierarchy_keys, list) and len(hierarchy_keys) >= 2:
            keys = [k for k in hierarchy_keys if isinstance(k, str) and k]
            for key in keys:
                ensure_lugar_node(key)
            for idx in range(len(keys) - 1):
                parents.add((keys[idx], keys[idx + 1]))
        elif place.get("parent_key"):
            parent_key = place["parent_key"]
            parents.add((place["lugar_key"], parent_key))
            ensure_lugar_node(parent_key)
            if parent_key != pais_key:
                parents.add((parent_key, pais_key))

        alias_key = f"alias:{field}:{registro}:{slugify_name(place['alias_norm'])}"
        aliases[alias_key] = {
            "alias_key": alias_key,
            "alias_norm": place["alias_norm"],
            "alias_raw": place["alias_raw"],
            "fuente": "detalles_personas",
            "campo_fuente": field,
            "tipo": place["tipo"],
            "parent_key": place.get("parent_key") or ALIAS_ROOT_PARENT_KEY,
            "lugar_key": place["lugar_key"],
            "tipo_entidad": "AliasLugar",
        }

        # Directly link persona to lugar with V1.1 temporal audit properties
        if persona_campo:
            tipo_relacion = "PRESENTE_EN"
            if persona_campo == "secuestro":
                tipo_relacion = "SECUESTRADO_EN"
            elif persona_campo == "nacimiento":
                tipo_relacion = "NACIO_EN"
            elif persona_campo == "asesinato":
                tipo_relacion = "ASESINADO_EN"

            persona_lugar_links.append(
                {
                    "persona_key": f"registro:{registro}",
                    "lugar_key": place["lugar_key"],
                    "tipo_relacion": tipo_relacion,
                    "fecha": fecha_event or "DESCONOCIDA",
                    "origen": "detalles_personas",
                }
            )

            # Check if there is a specific street address in text to represent as DirecciónCCD
            direccion = extract_specific_address(place.get("alias_raw"))
            if direccion is not None:
                strict_scope = f"{direccion['direccion_norm']}|{place['lugar_key']}"
                direccion_ccd_key = f"direccion_ccd:{hashlib.sha1(strict_scope.encode('utf-8')).hexdigest()[:20]}"
                direcciones[direccion_ccd_key] = {
                    "direccion_ccd_key": direccion_ccd_key,
                    "coordenadas": "DESCONOCIDAS",
                    "direccionExacta": direccion["direccion_raw"],
                    "lugar_key": place["lugar_key"],
                    "tipo_entidad": "DireccionCCD",
                }
                direccion_lugar_links.append(
                    {
                        "direccion_ccd_key": direccion_ccd_key,
                        "lugar_key": place["lugar_key"],
                        "tipo_relacion": "UBICADA_EN",
                    }
                )

    for item in data:
        registro = item.get("registro")
        if registro is None:
            continue
        detalle = item.get("detalle", {})

        fecha_sec = parse_ddmmyyyy(clean_text(detalle.get("descripcion_fecha_de_secuestro")))
        place_sec = resolve_place(
            detalle.get("descripcion_lugar_de_secuestro"),
            use_georef=use_georef,
            georef_catalog_path=georef_catalog_path,
            georef_min_score=georef_min_score,
            georef_ambiguity_delta=georef_ambiguity_delta,
        )
        if place_sec:
            register_place(
                place=place_sec,
                field="descripcion_lugar_de_secuestro",
                registro=registro,
                persona_campo="secuestro",
                fecha_event=fecha_sec,
            )

        fecha_nac = parse_ddmmyyyy(clean_text(detalle.get("descripcion_fecha_nacimiento")))
        place_nac = resolve_place(
            detalle.get("Lugar de nacimiento"),
            use_georef=use_georef,
            georef_catalog_path=georef_catalog_path,
            georef_min_score=georef_min_score,
            georef_ambiguity_delta=georef_ambiguity_delta,
        )
        if place_nac:
            register_place(
                place=place_nac,
                field="lugar_nacimiento",
                registro=registro,
                persona_campo="nacimiento",
                fecha_event=fecha_nac,
            )

        fecha_ase = parse_ddmmyyyy(clean_text(detalle.get("descripcion_fecha_de_asesinato")))
        place_ase = resolve_place(
            detalle.get("Lugar de asesinato"),
            use_georef=use_georef,
            georef_catalog_path=georef_catalog_path,
            georef_min_score=georef_min_score,
            georef_ambiguity_delta=georef_ambiguity_delta,
        )
        if place_ase:
            register_place(
                place=place_ase,
                field="lugar_asesinato",
                registro=registro,
                persona_campo="asesinato",
                fecha_event=fecha_ase,
            )

    parent_rows = [{"child_key": c, "parent_key": p, "tipo_relacion": "PARTE_DE"} for c, p in sorted(parents)]
    
    # Consolidate all geo entities under "lugares"
    all_places = list(lugares.values()) + list(aliases.values()) + list(direcciones.values())
    
    # Consolidate structural relations under "jerarquias"
    all_hierarchies = parent_rows + direccion_lugar_links

    return {
        "lugares": all_places,
        "eventos_espaciales": persona_lugar_links,
        "jerarquias": all_hierarchies,
    }


def _place_similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio()


def _is_safe_city_merge_name(name_a: str, name_b: str) -> tuple[bool, float, str]:
    if not name_a or not name_b or name_a == name_b:
        return (False, 0.0, "sin_cambio")

    nums_a = set(re.findall(r"\d+", name_a))
    nums_b = set(re.findall(r"\d+", name_b))
    if nums_a != nums_b:
        return (False, 0.0, "numeros_distintos")

    tokens_a = name_a.split()
    tokens_b = name_b.split()
    dirs_a = {t for t in tokens_a if t in DIRECTIONAL_TOKENS}
    dirs_b = {t for t in tokens_b if t in DIRECTIONAL_TOKENS}
    
    if dirs_a and dirs_b and dirs_a != dirs_b:
        return (False, 0.0, "direccion_conflictiva")
    if bool(dirs_a) != bool(dirs_b):
        return (False, 0.0, "direccion_incompleta")
    direction_bonus = 0.02 if dirs_a == dirs_b and dirs_a else 0.0

    if len(tokens_a) != len(tokens_b):
        return (False, 0.0, "estructura_distinta")

    mismatches = [(a, b) for a, b in zip(tokens_a, tokens_b) if a != b]
    if len(mismatches) != 1:
        return (False, 0.0, "muchas_diferencias")

    token_score = _place_similarity(mismatches[0][0], mismatches[0][1])
    full_score = _place_similarity(name_a, name_b)
    if token_score < 0.8 or full_score < 0.9:
        return (False, full_score, "diferencia_no_tipografica")

    return (True, min(1.0, full_score + direction_bonus), "typo_un_token")


def build_safe_place_merge_rows(lugar_layer: CanonicalDataset) -> List[Dict[str, Any]]:
    # Extract Lugar types and AliasLugar types from the consolidated list
    places_list = [x for x in lugar_layer.get("lugares", []) if x.get("tipo_entidad") == "Lugar"]
    aliases_list = [x for x in lugar_layer.get("lugares", []) if x.get("tipo_entidad") == "AliasLugar"]

    places = {row["lugar_key"]: row for row in places_list}
    aliases = aliases_list

    alias_count_by_place: Dict[str, int] = Counter(a["lugar_key"] for a in aliases)
    scope_by_place: Dict[str, tuple[str, str]] = {}
    for a in aliases:
        key = a["lugar_key"]
        if key not in scope_by_place:
            scope_by_place[key] = (a.get("tipo") or "", a.get("parent_key") or ALIAS_ROOT_PARENT_KEY)

    city_keys = [
        k
        for k, row in places.items()
        if row.get("tipoGeopolitico") == "CIUDAD" and k in scope_by_place and scope_by_place[k][1] != ALIAS_ROOT_PARENT_KEY
    ]
    scope_groups: Dict[tuple[str, str], List[str]] = defaultdict(list)
    for key in city_keys:
        scope_groups[scope_by_place[key]].append(key)

    parent: Dict[str, str] = {k: k for k in city_keys}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra == rb:
            return
        if ra < rb:
            parent[rb] = ra
        else:
            parent[ra] = rb

    evidence: Dict[tuple[str, str], tuple[float, str]] = {}
    for _, keys in scope_groups.items():
        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                ka, kb = keys[i], keys[j]
                na = str(places[ka].get("nombre") or "")
                nb = str(places[kb].get("nombre") or "")
                ok, score, reason = _is_safe_city_merge_name(na, nb)
                if not ok:
                    continue
                union(ka, kb)
                pair = (ka, kb) if ka < kb else (kb, ka)
                evidence[pair] = (score, reason)

    clusters: Dict[str, List[str]] = defaultdict(list)
    for k in city_keys:
        clusters[find(k)].append(k)

    rows: List[Dict[str, Any]] = []
    for _, keys in clusters.items():
        if len(keys) < 2:
            continue
        target = sorted(keys, key=lambda k: (-alias_count_by_place.get(k, 0), k))[0]
        for source in keys:
            if source == target:
                continue
            pair = (source, target) if source < target else (target, source)
            score, reason = evidence.get(pair, (0.91, "typo_cluster"))
            rows.append(
                {
                    "source_key": source,
                    "target_key": target,
                    "score": round(score, 3),
                    "reason": reason,
                }
            )
    return rows
