from __future__ import annotations

from typing import Any, Dict, List

from zona4_graph_loader.domain.text_norm import slugify_name


def build_v3_candidate_rows(
    detalles_personas: List[Dict[str, Any]],
    rel_familiares: List[Dict[str, Any]],
    rel_personas: List[Dict[str, Any]],
    rel_simult: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    placeholder_keys = {
        r["target_key"]
        for r in (rel_familiares + rel_personas + rel_simult)
        if r.get("target_placeholder") is True and str(r.get("target_key", "")).startswith("nombre:")
    }

    slug_to_candidates: Dict[str, List[str]] = {}
    for person in detalles_personas:
        key = person.get("persona_key")
        name = person.get("nombre_completo")
        if not key or not name:
            continue
        slug = slugify_name(name)
        slug_to_candidates.setdefault(slug, []).append(key)

    rows: List[Dict[str, Any]] = []
    for placeholder_key in sorted(placeholder_keys):
        slug = placeholder_key.split("nombre:", 1)[1]
        candidates = slug_to_candidates.get(slug, [])
        if not candidates:
            continue

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
    return rows
