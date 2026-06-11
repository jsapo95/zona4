from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List

from zona4_graph_loader.domain.name_similarity import name_similarity_score, name_token_set
from zona4_graph_loader.domain.text_norm import slugify_name


def build_v3_candidate_rows(
    detalles_personas: List[Dict[str, Any]],
    rel_familiares: List[Dict[str, Any]],
    rel_personas: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    fuzzy_threshold = 0.96
    max_fuzzy_slugs_per_placeholder = 3

    # Detect placeholders (keys starting with "nombre:")
    placeholder_keys = set()
    for r in (rel_familiares + rel_personas):
        for key_name in ("source_key", "target_key"):
            val = r.get(key_name, "")
            if isinstance(val, str) and val.startswith("nombre:"):
                placeholder_keys.add(val)

    slug_to_candidates: Dict[str, List[str]] = {}
    for person in detalles_personas:
        key = person.get("persona_key")
        name = person.get("nombre")  # V1.1 property name
        if not key or not name:
            continue
        slug = slugify_name(name)
        slug_to_candidates.setdefault(slug, []).append(key)

    candidate_slugs = sorted(slug_to_candidates.keys())
    candidate_token_sets = {slug: name_token_set(slug.replace("_", " ")) for slug in candidate_slugs}
    candidate_by_token: Dict[str, set[str]] = defaultdict(set)
    for candidate_slug, tokens in candidate_token_sets.items():
        for token in tokens:
            candidate_by_token[token].add(candidate_slug)

    rows: List[Dict[str, Any]] = []
    for placeholder_key in sorted(placeholder_keys):
        slug = placeholder_key.split("nombre:", 1)[1]
        candidates = slug_to_candidates.get(slug, [])
        if candidates:
            score = 1.0 if len(candidates) == 1 else 0.7
            confianza = "alta" if len(candidates) == 1 else "media"
            for candidate_key in candidates:
                rows.append(
                    {
                        "placeholder_key": placeholder_key,
                        "candidate_key": candidate_key,
                        "metodo": "slug_exacto",
                        "score": score,
                        "slug": slug,
                        "confianza": confianza,
                        "fuente": "v3_reconciliacion_asistida",
                    }
                )
            continue

        placeholder_name = slug.replace("_", " ")
        placeholder_tokens = name_token_set(placeholder_name)
        if not placeholder_tokens:
            continue

        candidate_pool: set[str] = set()
        for token in placeholder_tokens:
            candidate_pool.update(candidate_by_token.get(token, set()))
        if not candidate_pool:
            continue

        fuzzy_scored_slugs: list[tuple[float, str]] = []
        for candidate_slug in candidate_pool:
            token_count_diff = abs(len(candidate_token_sets[candidate_slug]) - len(placeholder_tokens))
            if token_count_diff > 2:
                continue
            score = name_similarity_score(placeholder_name, candidate_slug.replace("_", " "))
            if score >= fuzzy_threshold:
                fuzzy_scored_slugs.append((score, candidate_slug))

        fuzzy_scored_slugs.sort(key=lambda item: (-item[0], item[1]))
        for score, candidate_slug in fuzzy_scored_slugs[:max_fuzzy_slugs_per_placeholder]:
            confianza = "media" if score >= 0.985 else "baja"
            for candidate_key in slug_to_candidates[candidate_slug]:
                rows.append(
                    {
                        "placeholder_key": placeholder_key,
                        "candidate_key": candidate_key,
                        "metodo": "set_dice_typo_v1",
                        "score": round(score, 3),
                        "slug": slug,
                        "confianza": confianza,
                        "fuente": "v3_reconciliacion_asistida",
                    }
                )
    return rows
