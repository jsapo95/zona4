from __future__ import annotations

import difflib
import re
from collections import Counter, defaultdict
from typing import Any, Dict, List

from zona4_graph_loader.constants import ALIAS_ROOT_PARENT_KEY, DIRECTIONAL_TOKENS
from zona4_graph_loader.domain.place_norm import resolve_place
from zona4_graph_loader.domain.text_norm import slugify_name


def build_lugar_layer_rows(data: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    pais_key = "lugar:PAIS:argentina"
    lugares: Dict[str, Dict[str, Any]] = {
        pais_key: {
            "lugar_key": pais_key,
            "nombre_canonico": "ARGENTINA",
            "tipo": "PAIS",
            "pais_code": "AR",
            "fuente": "normalizacion_lugar",
        }
    }
    parents: set[tuple[str, str]] = set()
    aliases: Dict[str, Dict[str, Any]] = {}
    persona_links: list[Dict[str, Any]] = []
    evento_links: list[Dict[str, Any]] = []

    def register_place(place: Dict[str, Any], field: str, registro: int, evento_key: str | None, persona_campo: str | None) -> None:
        lugares[place["lugar_key"]] = {
            "lugar_key": place["lugar_key"],
            "nombre_canonico": place["nombre_canonico"],
            "tipo": place["tipo"],
            "pais_code": "AR",
            "fuente": "normalizacion_lugar",
        }
        if place.get("parent_key"):
            parent_key = place["parent_key"]
            parents.add((place["lugar_key"], parent_key))
            if parent_key not in lugares:
                prov_name = parent_key.split(":PROVINCIA:", 1)[1].split("|", 1)[0].replace("_", " ").upper()
                lugares[parent_key] = {
                    "lugar_key": parent_key,
                    "nombre_canonico": prov_name,
                    "tipo": "PROVINCIA",
                    "pais_code": "AR",
                    "fuente": "normalizacion_lugar",
                }
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
        }

        if persona_campo:
            persona_links.append(
                {
                    "registro": registro,
                    "lugar_key": place["lugar_key"],
                    "campo": persona_campo,
                    "fuente": "detalles_personas",
                    "alias_raw": place["alias_raw"],
                }
            )
        if evento_key:
            evento_links.append(
                {
                    "evento_key": evento_key,
                    "lugar_key": place["lugar_key"],
                    "fuente": "detalles_personas",
                    "campo_fuente": field,
                    "alias_raw": place["alias_raw"],
                }
            )

    for item in data:
        registro = item.get("registro")
        if registro is None:
            continue
        detalle = item.get("detalle", {})

        place_sec = resolve_place(detalle.get("descripcion_lugar_de_secuestro"))
        if place_sec:
            register_place(
                place=place_sec,
                field="descripcion_lugar_de_secuestro",
                registro=registro,
                evento_key=f"evento:detalles:secuestro:{registro}",
                persona_campo="secuestro",
            )

        place_nac = resolve_place(detalle.get("Lugar de nacimiento"))
        if place_nac:
            register_place(
                place=place_nac,
                field="lugar_nacimiento",
                registro=registro,
                evento_key=None,
                persona_campo="nacimiento",
            )

        place_ase = resolve_place(detalle.get("Lugar de asesinato"))
        if place_ase:
            register_place(
                place=place_ase,
                field="lugar_asesinato",
                registro=registro,
                evento_key=f"evento:detalles:asesinato:{registro}",
                persona_campo=None,
            )

    parent_rows = [{"child_key": c, "parent_key": p} for c, p in sorted(parents)]
    return {
        "lugares": list(lugares.values()),
        "aliases": list(aliases.values()),
        "parents": parent_rows,
        "persona_links": persona_links,
        "evento_links": evento_links,
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
    # Directional markers are protected tokens: conflicting or missing direction is unsafe.
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


def build_safe_place_merge_rows(lugar_layer: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    places = {row["lugar_key"]: row for row in lugar_layer.get("lugares", [])}
    aliases = lugar_layer.get("aliases", [])

    alias_count_by_place: Dict[str, int] = Counter(a["lugar_key"] for a in aliases)
    scope_by_place: Dict[str, tuple[str, str]] = {}
    for a in aliases:
        key = a["lugar_key"]
        if key not in scope_by_place:
            scope_by_place[key] = (a.get("tipo") or "", a.get("parent_key") or ALIAS_ROOT_PARENT_KEY)

    city_keys = [
        k
        for k, row in places.items()
        if row.get("tipo") == "CIUDAD" and k in scope_by_place and scope_by_place[k][1] != ALIAS_ROOT_PARENT_KEY
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
                na = str(places[ka].get("nombre_canonico") or "")
                nb = str(places[kb].get("nombre_canonico") or "")
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
