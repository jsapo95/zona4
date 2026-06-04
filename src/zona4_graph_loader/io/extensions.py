from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Canonical row collections accepted by the V1.1 loader pipeline.
ALLOWED_EXTENSION_KEYS = {
    "personas_detalles",
    "protagonistas",
    "rel_familiares",
    "rel_personas",
    "lugares",
    "aliases",
    "direcciones",
    "parents",
    "persona_lugar_links",
    "direccion_lugar_links",
}

METADATA_KEYS = {"source_id", "description", "version"}


def empty_extension_collections() -> Dict[str, List[Dict[str, Any]]]:
    return {key: [] for key in sorted(ALLOWED_EXTENSION_KEYS)}


def load_extension_collections(extensions_dir: Path) -> Tuple[Dict[str, List[Dict[str, Any]]], List[Path]]:
    """Load extension bundles from a directory and merge them by collection key."""
    merged = empty_extension_collections()
    loaded_files: List[Path] = []

    if not extensions_dir.exists() or not extensions_dir.is_dir():
        return merged, loaded_files

    for file_path in sorted(extensions_dir.glob("*.json")):
        with file_path.open("r", encoding="utf-8") as f:
            payload = json.load(f)

        if not isinstance(payload, dict):
            raise ValueError(f"Extension file must contain a JSON object: {file_path}")

        for key, rows in payload.items():
            if key in METADATA_KEYS:
                continue
            if key not in ALLOWED_EXTENSION_KEYS:
                raise ValueError(
                    f"Unknown extension key '{key}' in {file_path}. "
                    f"Allowed keys: {', '.join(sorted(ALLOWED_EXTENSION_KEYS))}"
                )
            if rows is None:
                continue
            if not isinstance(rows, list):
                raise ValueError(f"Extension key '{key}' must be a list in {file_path}")

            bad_row = next((row for row in rows if not isinstance(row, dict)), None)
            if bad_row is not None:
                raise ValueError(f"Extension key '{key}' must contain only objects in {file_path}")

            merged[key].extend(rows)

        loaded_files.append(file_path)

    return merged, loaded_files
