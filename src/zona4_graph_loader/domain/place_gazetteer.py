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

    def _collect_explicit_provinces(self, tokens: List[str]) -> Tuple[set[str], Dict[str, set[str]]]:
        """Provincias que el texto nombra, y nombres de provincia que en el
        texto sólo aparecen como calle.

        Una calle o esquina con nombre de provincia ("San Luis 2535", "Av.
        Santa Fe", "Entre Ríos y La Rioja") no es una pista de provincia: si
        se la tomara como tal, los candidatos quedarían restringidos a esa
        provincia y se descartaría la ciudad que el texto nombra ("...
        Gral. Pueyrredón. Mar del Plata", "(Quilmes)"). Esto sólo se aplica
        cuando ningún nombre de provincia del texto funciona como pista: si
        alguno lo hace ("... · POSADAS · CAPITAL · MISIONES"), se conserva
        el criterio de siempre y las calles se tratan en
        `_drop_province_homonyms`.

        Devuelve `(provincias, calles)`, con `calles` = {nombre: ids de la
        provincia homónima}; `calles` sólo tiene algo cuando `provincias`
        quedó vacío.
        """
        province_ids: set[str] = set()
        calles: Dict[str, set[str]] = {}
        hay_pista = False
        for name_norm, records in self._province_records_by_name.items():
            if len(name_norm) < 4:
                continue
            ocurrencias = self._occurrences(tokens, name_norm)
            if not ocurrencias:
                continue
            ids = {rec.provincia_id for rec in records}
            province_ids |= ids
            if all(self._es_calle(tokens, start, end) for start, end in ocurrencias):
                calles[name_norm] = ids
            else:
                hay_pista = True
        if hay_pista or not calles:
            return province_ids, {}
        return set(), calles

    @staticmethod
    def _occurrences(tokens: List[str], name_norm: str) -> List[Tuple[int, int]]:
        name_tokens = name_norm.split()
        size = len(name_tokens)
        return [
            (start, start + size)
            for start in range(0, len(tokens) - size + 1)
            if tokens[start : start + size] == name_tokens
        ]

    def _es_calle(self, tokens: List[str], start: int, end: int) -> bool:
        if self._address_context_penalty(tokens, start, end) > 0:
            return True
        return (start > 0 and tokens[start - 1] == "Y") or (end < len(tokens) and tokens[end] == "Y")

    def _drop_province_homonyms(
        self, matches: List[PlaceMatch], tokens: List[str], explicit_province_ids: set[str], min_score: float
    ) -> List[PlaceMatch]:
        """Un nombre que funciona como pista de provincia no puede ser además
        la ciudad homónima (la capital).

        "GOYA. CORRIENTES" matchea dos localidades de Corrientes: Goya y la
        ciudad de Corrientes. "CORRIENTES" ya se usó como pista de provincia
        (es lo que restringe los candidatos a Corrientes), así que no puede
        ser además la ciudad: si el texto nombra otro lugar, gana ése. Antes,
        el desempate por largo de nombre o por cantidad de palabras ("SANTA
        FE" son dos) mandaba a la capital textos como "ROSARIO. SANTA FE",
        "CHAMICAL. LA RIOJA" o "PIRANE. FORMOSA".

        - La capital se mantiene si no hay ningún otro lugar ("SALTA",
          "SALTA. SALTA"). No cuentan como otro lugar la propia provincia ni
          el departamento que contiene a la capital ("LA CAPITAL", "CAPITAL").
        - La capital se mantiene si la fuente la nombra como tal: el nombre
          va seguido de "CAPITAL" ("Colón, Córdoba Capital") o aparece dos
          veces en un texto que dice "CAPITAL" ("SANTA FE · LA CAPITAL ·
          SANTA FE"). En ese caso la capital cuenta como otro lugar para las
          demás homónimas ("LERMA entre LA RIOJA y SAN LUIS · SALTA ·
          CAPITAL · SALTA" queda en la ciudad de Salta).
        - Si los otros lugares son todos de otra provincia, el nombre no era
          una pista de provincia sino una calle o parte de otro nombre
          ("Ingenio San Juan, Cruz Alta, Tucumán"; "Córdoba 84 · Oliveros ·
          Santa Fe"): se descarta también la provincia homónima.
        """
        if not explicit_province_ids:
            return matches
        hint_names = {self._province_name_by_id[pid] for pid in explicit_province_ids if pid in self._province_name_by_id}

        def es_homonima(m: PlaceMatch) -> bool:
            return m.level != "PROVINCIA" and m.name == m.provincia_name and m.name in hint_names

        homonimas = [m for m in matches if es_homonima(m)]
        if not homonimas:
            return matches

        dice_capital = "CAPITAL" in tokens
        nombradas_como_capital: set[str] = set()
        for nombre in {m.name for m in homonimas}:
            ocurrencias = self._occurrences(tokens, nombre)
            seguida_de_capital = any(end < len(tokens) and tokens[end] == "CAPITAL" for _start, end in ocurrencias)
            if seguida_de_capital or (dice_capital and len(ocurrencias) >= 2):
                nombradas_como_capital.add(nombre)

        departamentos_capital = {m.departamento_name for m in homonimas if m.departamento_name}
        otros_lugares = [
            m
            for m in matches
            if m.level != "PROVINCIA"
            and (not es_homonima(m) or m.name in nombradas_como_capital)
            and m.name not in departamentos_capital
            and m.score >= min_score
        ]

        def se_descarta(m: PlaceMatch) -> bool:
            if m.name in nombradas_como_capital:
                return False
            otros = [o for o in otros_lugares if o.name != m.name]
            if not otros:
                return False
            if es_homonima(m):
                return True
            # La provincia homónima de una capital descartada: sólo sigue
            # siendo pista si el texto nombra otro lugar de esa provincia.
            return (
                m.level == "PROVINCIA"
                and m.name in {h.name for h in homonimas}
                and all(o.provincia_name != m.name for o in otros)
            )

        return [m for m in matches if not se_descarta(m)]

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

        explicit_province_ids, calles = self._collect_explicit_provinces(tokens)
        if not calles:
            return self._resolve_tokens(
                tokens, explicit_province_ids, min_score=min_score, ambiguity_delta=ambiguity_delta
            )

        # La otra calle de una esquina con nombre de provincia ("San Luis y
        # Pellegrini") tampoco es un lugar.
        bloqueados: set[Tuple[int, int]] = set()
        for nombre in calles:
            for start, end in self._occurrences(tokens, nombre):
                bloqueados.add((start, end))
                if end < len(tokens) and tokens[end] == "Y":
                    bloqueados |= {(end + 1, fin) for fin in range(end + 2, len(tokens) + 1)}
                if start > 0 and tokens[start - 1] == "Y":
                    bloqueados |= {(ini, start - 1) for ini in range(0, start - 1)}
        match = self._resolve_tokens(
            tokens, set(), bloqueados=bloqueados, min_score=min_score, ambiguity_delta=ambiguity_delta
        )
        if match is None:
            # Sin las calles no quedó ningún lugar ("Entre San Juan y
            # Córdoba"): se conserva el resultado de antes, que trataba esos
            # nombres como pistas de provincia.
            antes_ids: set[str] = set()
            for ids in calles.values():
                antes_ids |= ids
            match = self._resolve_tokens(tokens, antes_ids, min_score=min_score, ambiguity_delta=ambiguity_delta)
        return match

    def _resolve_tokens(
        self,
        tokens: List[str],
        explicit_province_ids: set[str],
        *,
        bloqueados: Optional[set[Tuple[int, int]]] = None,
        min_score: float,
        ambiguity_delta: float,
    ) -> Optional[PlaceMatch]:
        matches: List[PlaceMatch] = []

        for gram, size, start, end in self._iter_ngrams(tokens):
            if size == 1 and len(gram) < 4:
                continue
            if bloqueados and (start, end) in bloqueados:
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

        matches = self._drop_province_homonyms(matches, tokens, explicit_province_ids, min_score)
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

