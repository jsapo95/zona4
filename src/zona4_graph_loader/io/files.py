from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT / "data"
LISTADO_PAGINAS_PATH = DATA_DIR / "listado_paginas.json"
DETALLES_PATH = DATA_DIR / "parque_de_la_memoria.json"
NIETXS_PATH = DATA_DIR / "nietos_y_nietas.json"


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)
