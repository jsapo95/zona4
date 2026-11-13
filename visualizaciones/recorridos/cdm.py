"""Obtiene el CDM consolidado del pipeline del equipo sin Neo4j.

Corre `pipeline.load_graph.run_load` tal cual hasta el `--dump-cdm` (builders,
resolución de lugares y resolución de identidades) y corta ahí. Dos ajustes,
ninguno cambia el contenido del CDM:

1. Se saltea el Paso 2 de `resolve_identities` (candidatos fuzzy). Ese paso
   sólo agrega `CANDIDATO_MERGE`, nunca fusiona personas, y es el que hace que
   la carga completa tarde más de media hora. Las fusiones del Paso 1 quedan
   idénticas.
2. Corre en un directorio temporal para que `run_load` no reescriba
   `data/processed/identity_merges.json`, que está versionado.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict
from unittest import mock

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

from zona4_graph_loader.cli import parse_args  # noqa: E402
from zona4_graph_loader.domain import identity_resolution  # noqa: E402
from zona4_graph_loader.pipeline import load_graph  # noqa: E402


class _CDMListo(Exception):
    """Se lanza al llegar a la configuración de Neo4j: el CDM ya está escrito."""


def construir_cdm() -> Dict[str, Any]:
    directorio_original = Path.cwd()
    with tempfile.TemporaryDirectory() as tmp:
        salida = Path(tmp) / "cdm.json"
        argv = [
            "cdm",
            "--dump-cdm", str(salida),
            "--skip-qa-report",
            "--georef-catalog-path", str(RAIZ / "data" / "processed" / "georef_catalog.json"),
            "--sources-dir", str(RAIZ / "data" / "sources"),
        ]
        with mock.patch.object(sys, "argv", argv):
            args = parse_args()
        os.chdir(tmp)
        try:
            with mock.patch.object(identity_resolution, "name_similarity_score", lambda a, b: 0.0), \
                 mock.patch.object(load_graph, "get_config", side_effect=_CDMListo):
                load_graph.run_load(args)
        except _CDMListo:
            pass
        finally:
            os.chdir(directorio_original)
        with salida.open(encoding="utf-8") as f:
            return json.load(f)
