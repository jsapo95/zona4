from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from zona4_graph_loader.constants import PROVINCE_PRIORITY
from zona4_graph_loader.domain.text_norm import norm_space, strip_accents


def _norm_geo_name(value: str) -> str:
    text = strip_accents(value.upper())
    cleaned = []
    for ch in text:
        if ch.isalnum() or ch.isspace():
            cleaned.append(ch)
        else:
            cleaned.append(" ")
    return norm_space("".join(cleaned))


@dataclass(frozen=True)
class GeoRecord:
    level: str
    entity_id: str
    name: str
    name_norm: str
    provincia_id: str
    provincia_name: str
    departamento_id: Optional[str] = None
    departamento_name: Optional[str] = None


@dataclass(frozen=True)
class PlaceMatch:
    score: float
    level: str
    name: str
    provincia_name: str
    departamento_name: Optional[str] = None


class PlaceGazetteer:
    def __init__(self, catalog: Dict[str, Any]) -> None:
        self._province_records_by_name: Dict[str, List[GeoRecord]] = {}
        self._department_records_by_name: Dict[str, List[GeoRecord]] = {}
        self._municipio_records_by_name: Dict[str, List[GeoRecord]] = {}
        self._localidad_records_by_name: Dict[str, List[GeoRecord]] = {}
        self._province_name_by_id: Dict[str, str] = {}
        self._department_name_by_id: Dict[str, str] = {}
        self._province_rank: Dict[str, int] = {
            _norm_geo_name(name): rank for rank, name in enumerate(PROVINCE_PRIORITY)
        }

        self._build_indexes(catalog)

    @classmethod
    def from_file(cls, path: Path) -> "PlaceGazetteer":
        with path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
        return cls(payload)

    def _build_indexes(self, catalog: Dict[str, Any]) -> None:
        for prov in catalog.get("provincias", []):
            prov_id = str(prov.get("id") or "")
            prov_name = str(prov.get("nombre") or "")
            if not prov_id or not prov_name:
                continue
            prov_name_norm = _norm_geo_name(prov_name)
            self._province_name_by_id[prov_id] = prov_name_norm
            self._province_records_by_name.setdefault(prov_name_norm, []).append(
                GeoRecord(
                    level="PROVINCIA",
                    entity_id=prov_id,
                    name=prov_name_norm,
                    name_norm=prov_name_norm,
                    provincia_id=prov_id,
                    provincia_name=prov_name_norm,
                )
            )

        self._load_children(catalog.get("departamentos", []), level="DEPARTAMENTO")
        self._load_children(catalog.get("municipios", []), level="MUNICIPIO")
        self._load_children(catalog.get("localidades", []), level="LOCALIDAD")

    def _load_children(self, rows: Iterable[Dict[str, Any]], level: str) -> None:
        target = {
            "DEPARTAMENTO": self._department_records_by_name,
            "MUNICIPIO": self._municipio_records_by_name,
            "LOCALIDAD": self._localidad_records_by_name,
        }[level]

        for row in rows:
            entity_id = str(row.get("id") or "")
            name = str(row.get("nombre") or "")
            provincia_id = str(row.get("provincia_id") or "")
            if not entity_id or not name or not provincia_id:
                continue
            prov_name_norm = self._province_name_by_id.get(provincia_id)
            if not prov_name_norm:
                continue
            name_norm = _norm_geo_name(name)
            departamento_id: Optional[str]
            departamento_name: Optional[str]
            if level == "DEPARTAMENTO":
                departamento_id = entity_id
                departamento_name = name_norm
                self._department_name_by_id[entity_id] = name_norm
            else:
                dep_id_raw = str(row.get("departamento_id") or "")
                departamento_id = dep_id_raw or None
                departamento_name = self._department_name_by_id.get(dep_id_raw) if dep_id_raw else None
            target.setdefault(name_norm, []).append(
                GeoRecord(
                    level=level,
                    entity_id=entity_id,
                    name=name_norm,
                    name_norm=name_norm,
                    provincia_id=provincia_id,
                    provincia_name=prov_name_norm,
                    departamento_id=departamento_id,
                    departamento_name=departamento_name,
                )
            )

    def _iter_ngrams(self, tokens: List[str], max_len: int = 6) -> Iterable[Tuple[str, int, int, int]]:
        n_tokens = len(tokens)
        for size in range(min(max_len, n_tokens), 0, -1):
            for i in range(0, n_tokens - size + 1):
                gram = " ".join(tokens[i : i + size])
                yield gram, size, i, i + size

    def _address_context_penalty(self, tokens: List[str], start: int, end: int) -> float:
        # Penalize grams that look like street/address fragments to avoid false positives.
        if not tokens:
            return 0.0
        address_prefix_tokens = {
            "CALLE",
            "AV",
            "AVENIDA",
            "RUTA",
            "PASAJE",
            "PJE",
            "NRO",
            "NUMERO",
        }
        penalty = 0.0
        if start > 0 and tokens[start - 1] in address_prefix_tokens:
            penalty += 0.12
        if end < len(tokens) and tokens[end].isdigit():
            penalty += 0.10
        return penalty

    def _province_prior(self, provincia_name_norm: str) -> float:
        rank = self._province_rank.get(provincia_name_norm)
        if rank is None:
            return 0.0
        # Earlier rank means larger province; cap effect so text evidence dominates.
        return max(0.0, 0.14 - (rank * 0.004))

    def _collect_explicit_provinces(self, alias_norm: str) -> set[str]:
        padded = f" {alias_norm} "
        province_ids: set[str] = set()
        for name_norm, records in self._province_records_by_name.items():
            if len(name_norm) < 4:
                continue
            if f" {name_norm} " in padded:
                for rec in records:
                    province_ids.add(rec.provincia_id)
        return province_ids

    def resolve_admin_context(self, context_norm: str, *, preferred_province_name: Optional[str] = None) -> Optional[GeoRecord]:
        ctx = _norm_geo_name(context_norm)
        if not ctx:
            return None

        candidates: List[GeoRecord] = []
        candidates.extend(self._municipio_records_by_name.get(ctx, []))
        candidates.extend(self._department_records_by_name.get(ctx, []))
        candidates.extend(self._province_records_by_name.get(ctx, []))
        if not candidates:
            return None

        preferred = _norm_geo_name(preferred_province_name) if preferred_province_name else None
        if preferred:
            preferred_candidates = [c for c in candidates if c.provincia_name == preferred]
            if preferred_candidates:
                candidates = preferred_candidates

        level_rank = {"MUNICIPIO": 3, "DEPARTAMENTO": 2, "PROVINCIA": 1}
        ranked = sorted(
            candidates,
            key=lambda c: (level_rank.get(c.level, 0), self._province_prior(c.provincia_name)),
            reverse=True,
        )
        return ranked[0]

    def resolve(self, alias_norm: str, min_score: float = 0.76, ambiguity_delta: float = 0.08) -> Optional[PlaceMatch]:
        tokens = [tok for tok in alias_norm.split() if tok]
        if not tokens:
            return None

        explicit_province_ids = self._collect_explicit_provinces(alias_norm)
        matches: List[PlaceMatch] = []

        for gram, size, start, end in self._iter_ngrams(tokens):
            if size == 1 and len(gram) < 4:
                continue
            context_penalty = self._address_context_penalty(tokens, start, end)

            for rec in self._localidad_records_by_name.get(gram, []):
                if explicit_province_ids and rec.provincia_id not in explicit_province_ids:
                    continue
                score = 0.80 + min(0.15, size * 0.02)
                if explicit_province_ids:
                    score += 0.06
                else:
                    score += self._province_prior(rec.provincia_name)
                score -= context_penalty
                matches.append(
                    PlaceMatch(
                        score=score,
                        level="LOCALIDAD",
                        name=rec.name,
                        provincia_name=rec.provincia_name,
                        departamento_name=rec.departamento_name,
                    )
                )

            for rec in self._municipio_records_by_name.get(gram, []):
                if explicit_province_ids and rec.provincia_id not in explicit_province_ids:
                    continue
                score = 0.76 + min(0.12, size * 0.02)
                if explicit_province_ids:
                    score += 0.06
                else:
                    score += self._province_prior(rec.provincia_name)
                score -= context_penalty
                matches.append(
                    PlaceMatch(
                        score=score,
                        level="MUNICIPIO",
                        name=rec.name,
                        provincia_name=rec.provincia_name,
                        departamento_name=rec.departamento_name,
                    )
                )

            for rec in self._department_records_by_name.get(gram, []):
                if explicit_province_ids and rec.provincia_id not in explicit_province_ids:
                    continue
                score = 0.71 + min(0.12, size * 0.02)
                if explicit_province_ids:
                    score += 0.05
                else:
                    score += self._province_prior(rec.provincia_name)
                score -= context_penalty
                matches.append(
                    PlaceMatch(
                        score=score,
                        level="DEPARTAMENTO",
                        name=rec.name,
                        provincia_name=rec.provincia_name,
                        departamento_name=rec.name,
                    )
                )

            for rec in self._province_records_by_name.get(gram, []):
                score = 0.75 + min(0.10, size * 0.02)
                matches.append(
                    PlaceMatch(
                        score=score,
                        level="PROVINCIA",
                        name=rec.name,
                        provincia_name=rec.provincia_name,
                        departamento_name=None,
                    )
                )

        if not matches:
            return None

        dedup: Dict[Tuple[str, str], PlaceMatch] = {}
        level_rank = {"LOCALIDAD": 4, "MUNICIPIO": 3, "DEPARTAMENTO": 2, "PROVINCIA": 1}
        for m in matches:
            key = (m.name, m.provincia_name, m.departamento_name or "")
            prev = dedup.get(key)
            if prev is None:
                dedup[key] = m
                continue
            if (m.score > prev.score) or (
                m.score == prev.score and level_rank.get(m.level, 0) > level_rank.get(prev.level, 0)
            ):
                dedup[key] = m

        ranked = sorted(dedup.values(), key=lambda m: (m.score, len(m.name)), reverse=True)
        best = ranked[0]
        second = ranked[1] if len(ranked) > 1 else None

        if best.score < min_score:
            return None
        if second is not None and (best.score - second.score) < ambiguity_delta:
            # If both top candidates point to the same province, keep the best one
            # instead of dropping to unknown; this is common in nested toponyms.
            if best.provincia_name != second.provincia_name:
                return None

        return best

