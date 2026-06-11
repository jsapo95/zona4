from __future__ import annotations

import re
from difflib import SequenceMatcher

from zona4_graph_loader.domain.text_norm import norm_space, strip_accents

TRASH_TOKENS = {
    "de",
    "del",
    "la",
    "las",
    "el",
    "los",
    "y",
    "mr",
    "mrs",
    "miss",
    "ms",
    "da",
    "junior",
    "jr",
    "das",
    "di",
    "van",
    "der",
    "dos",
    "filho",
    "do",
}

PROTECTED_TOKENS = {"este", "oeste", "norte", "sur"}


def _levenshtein_distance(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)

    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        current = [i]
        for j, cb in enumerate(b, start=1):
            ins = current[j - 1] + 1
            dele = previous[j] + 1
            sub = previous[j - 1] + (ca != cb)
            current.append(min(ins, dele, sub))
        previous = current
    return previous[-1]


def _to_token_set(value: str) -> set[str]:
    text = strip_accents(value.lower().replace("_", " "))
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = norm_space(text)
    if not text:
        return set()
    return set(text.split(" "))


def name_token_set(value: str) -> set[str]:
    return _remove_trash(_to_token_set(value))


def _remove_trash(tokens: set[str]) -> set[str]:
    dynamic_drop = {token for token in tokens if len(token) == 1}
    return {token for token in tokens if token not in TRASH_TOKENS and token not in dynamic_drop}


def _is_numeric_token(token: str) -> bool:
    return token.isdigit()


def _typo_correction(source: set[str], target: set[str], max_distance: int = 1) -> set[str]:
    corrected: set[str] = set()
    for source_token in source:
        if source_token in PROTECTED_TOKENS or _is_numeric_token(source_token):
            corrected.add(source_token)
            continue

        best_token = source_token
        for target_token in target:
            if target_token in PROTECTED_TOKENS or _is_numeric_token(target_token):
                continue
            if abs(len(source_token) - len(target_token)) > max_distance:
                continue
            if _levenshtein_distance(source_token, target_token) <= max_distance:
                best_token = target_token
                break
        corrected.add(best_token)
    return corrected


def _soft_sorensen_dice(set1: set[str], set2: set[str], threshold: float = 0.84) -> float:
    if not set1 or not set2:
        return 0.0

    exact = set1.intersection(set2)
    remaining1 = list(set1 - exact)
    remaining2 = list(set2 - exact)
    used_indices: set[int] = set()

    soft_matches = 0.0
    for token1 in remaining1:
        best_score = 0.0
        best_idx: int | None = None
        for idx, token2 in enumerate(remaining2):
            if idx in used_indices:
                continue
            score = SequenceMatcher(None, token1, token2).ratio()
            if score > best_score:
                best_score = score
                best_idx = idx
        if best_idx is not None and best_score >= threshold:
            soft_matches += best_score
            used_indices.add(best_idx)

    return (2.0 * (len(exact) + soft_matches)) / (len(set1) + len(set2))


def name_similarity_score(name1: str, name2: str, threshold: float = 0.84) -> float:
    tokens1 = name_token_set(name1)
    tokens2 = name_token_set(name2)
    if not tokens1 or not tokens2:
        return 0.0

    directions1 = tokens1.intersection(PROTECTED_TOKENS)
    directions2 = tokens2.intersection(PROTECTED_TOKENS)
    if directions1 != directions2 and (directions1 or directions2):
        return 0.0

    nums1 = {token for token in tokens1 if _is_numeric_token(token)}
    nums2 = {token for token in tokens2 if _is_numeric_token(token)}
    if nums1 != nums2 and (nums1 or nums2):
        return 0.0

    corrected1 = _typo_correction(tokens1, tokens2)
    corrected2 = _typo_correction(tokens2, tokens1)
    score12 = _soft_sorensen_dice(corrected1, tokens2, threshold=threshold)
    score21 = _soft_sorensen_dice(corrected2, tokens1, threshold=threshold)
    return round((score12 + score21) / 2.0, 6)
