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


@dataclass(frozen=True)
class PlaceMatch:
    score: float
    level: str
    name: str
    provincia_name: str


class PlaceGazetteer:
    def __init__(self, catalog: Dict[str, Any]) -> None:
        self._province_records_by_name: Dict[str, List[GeoRecord]] = {}
        self._department_records_by_name: Dict[str, List[GeoRecord]] = {}
        self._municipio_records_by_name: Dict[str, List[GeoRecord]] = {}
        self._localidad_records_by_name: Dict[str, List[GeoRecord]] = {}
        self._province_name_by_id: Dict[str, str] = {}
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
            target.setdefault(name_norm, []).append(
                GeoRecord(
                    level=level,
                    entity_id=entity_id,
                    name=name_norm,
                    name_norm=name_norm,
                    provincia_id=provincia_id,
                    provincia_name=prov_name_norm,
                )
            )

    def _iter_ngrams(self, tokens: List[str], max_len: int = 6) -> Iterable[Tuple[str, int]]:
        n_tokens = len(tokens)
        for size in range(min(max_len, n_tokens), 0, -1):
            for i in range(0, n_tokens - size + 1):
                gram = " ".join(tokens[i : i + size])
                yield gram, size

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

    def resolve(self, alias_norm: str, min_score: float = 0.76, ambiguity_delta: float = 0.08) -> Optional[PlaceMatch]:
        tokens = [tok for tok in alias_norm.split() if tok]
        if not tokens:
            return None

        explicit_province_ids = self._collect_explicit_provinces(alias_norm)
        matches: List[PlaceMatch] = []

        for gram, size in self._iter_ngrams(tokens):
            if size == 1 and len(gram) < 4:
                continue

            for rec in self._localidad_records_by_name.get(gram, []):
                if explicit_province_ids and rec.provincia_id not in explicit_province_ids:
                    continue
                score = 0.80 + min(0.15, size * 0.02)
                if explicit_province_ids:
                    score += 0.06
                else:
                    score += self._province_prior(rec.provincia_name)
                matches.append(PlaceMatch(score=score, level="LOCALIDAD", name=rec.name, provincia_name=rec.provincia_name))

            for rec in self._municipio_records_by_name.get(gram, []):
                if explicit_province_ids and rec.provincia_id not in explicit_province_ids:
                    continue
                score = 0.76 + min(0.12, size * 0.02)
                if explicit_province_ids:
                    score += 0.06
                else:
                    score += self._province_prior(rec.provincia_name)
                matches.append(PlaceMatch(score=score, level="MUNICIPIO", name=rec.name, provincia_name=rec.provincia_name))

            for rec in self._department_records_by_name.get(gram, []):
                if explicit_province_ids and rec.provincia_id not in explicit_province_ids:
                    continue
                score = 0.71 + min(0.12, size * 0.02)
                if explicit_province_ids:
                    score += 0.05
                else:
                    score += self._province_prior(rec.provincia_name)
                matches.append(PlaceMatch(score=score, level="DEPARTAMENTO", name=rec.name, provincia_name=rec.provincia_name))

            for rec in self._province_records_by_name.get(gram, []):
                score = 0.75 + min(0.10, size * 0.02)
                matches.append(PlaceMatch(score=score, level="PROVINCIA", name=rec.name, provincia_name=rec.provincia_name))

        if not matches:
            return None

        dedup: Dict[Tuple[str, str], PlaceMatch] = {}
        level_rank = {"LOCALIDAD": 4, "MUNICIPIO": 3, "DEPARTAMENTO": 2, "PROVINCIA": 1}
        for m in matches:
            key = (m.name, m.provincia_name)
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
            return None

        return best

