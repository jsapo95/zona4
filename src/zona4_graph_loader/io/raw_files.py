from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[3]
RAW_DIR = ROOT / "data" / "raw"


def read_raw_json(nombre: str) -> Any:
    with (RAW_DIR / nombre).open("r", encoding="utf-8") as f:
        return json.load(f)


def read_raw_csv(nombre: str, delimiter: str = ";") -> List[Dict[str, str]]:
    with (RAW_DIR / nombre).open("r", encoding="utf-8", newline="") as f:
        return [dict(row) for row in csv.DictReader(f, delimiter=delimiter)]
