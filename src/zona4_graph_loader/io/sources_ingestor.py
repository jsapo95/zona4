from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Canonical keys under Variant 1 CDM
ALLOWED_SOURCE_KEYS = {
    "personas",
    "lugares",
    "relaciones_interpersonales",
    "eventos_espaciales",
    "jerarquias",
}

METADATA_KEYS = {"source_id", "description", "version"}

# Base source filenames processed by dedicated builders (should be skipped by the direct JSON loader)
BASE_SOURCE_FILENAMES = {
    "ccds.json",
    "nietos_y_nietas.json",
    "parque_de_la_memoria.json",
    "listado_paginas.json",
    "georef_catalog.json",
}


def empty_canonical_dataset() -> Dict[str, List[Dict[str, Any]]]:
    return {key: [] for key in sorted(ALLOWED_SOURCE_KEYS)}


def load_direct_sources(sources_dir: Path) -> Tuple[Dict[str, List[Dict[str, Any]]], List[Path]]:
    """Load direct static JSON sources conforming to the Variant 1 CDM, skipping builder-backed files."""
    merged = empty_canonical_dataset()
    loaded_files: List[Path] = []

    if not sources_dir.exists() or not sources_dir.is_dir():
        return merged, loaded_files

    for file_path in sorted(sources_dir.glob("*.json")):
        if file_path.name in BASE_SOURCE_FILENAMES:
            continue

        with file_path.open("r", encoding="utf-8") as f:
            payload = json.load(f)

        if not isinstance(payload, dict):
            raise ValueError(f"Direct source file must contain a JSON object: {file_path}")

        for key, rows in payload.items():
            if key in METADATA_KEYS:
                continue
            if key not in ALLOWED_SOURCE_KEYS:
                raise ValueError(
                    f"Unknown source key '{key}' in {file_path}. "
                    f"Allowed keys: {', '.join(sorted(ALLOWED_SOURCE_KEYS))}"
                )
            if rows is None:
                continue
            if not isinstance(rows, list):
                raise ValueError(f"Source key '{key}' must be a list in {file_path}")

            bad_row = next((row for row in rows if not isinstance(row, dict)), None)
            if bad_row is not None:
                raise ValueError(f"Source key '{key}' must contain only objects in {file_path}")

            merged[key].extend(rows)

        loaded_files.append(file_path)

    return merged, loaded_files
