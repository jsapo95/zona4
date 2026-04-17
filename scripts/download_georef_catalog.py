#!/usr/bin/env python3
"""Descarga un catalogo local de Georef para resolver lugares offline."""

from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

API_ROOT = "https://apis.datos.gob.ar/georef/api"


def _fetch_json(url: str, timeout: int) -> Dict[str, Any]:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_all(resource: str, campos: str, timeout: int, page_size: int = 5000) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    inicio = 0
    total = None

    while total is None or inicio < total:
        params = {
            "campos": campos,
            "max": str(page_size),
            "inicio": str(inicio),
        }
        url = f"{API_ROOT}/{resource}?{urllib.parse.urlencode(params)}"
        payload = _fetch_json(url, timeout=timeout)
        batch = payload.get(resource, [])
        if not isinstance(batch, list):
            raise RuntimeError(f"Respuesta invalida para {resource}")
        rows.extend(batch)
        total = int(payload.get("total", len(rows)))
        inicio += page_size
        if not batch:
            break

    return rows


def build_catalog(timeout: int) -> Dict[str, Any]:
    provincias = fetch_all("provincias", "id,nombre", timeout)
    departamentos_raw = fetch_all("departamentos", "id,nombre,provincia.id", timeout)
    municipios_raw = fetch_all("municipios", "id,nombre,provincia.id", timeout)
    localidades_raw = fetch_all(
        "localidades",
        "id,nombre,provincia.id,departamento.id,municipio.id",
        timeout,
    )

    departamentos = [
        {
            "id": row.get("id"),
            "nombre": row.get("nombre"),
            "provincia_id": (row.get("provincia") or {}).get("id"),
        }
        for row in departamentos_raw
    ]
    municipios = [
        {
            "id": row.get("id"),
            "nombre": row.get("nombre"),
            "provincia_id": (row.get("provincia") or {}).get("id"),
        }
        for row in municipios_raw
    ]
    localidades = [
        {
            "id": row.get("id"),
            "nombre": row.get("nombre"),
            "provincia_id": (row.get("provincia") or {}).get("id"),
            "departamento_id": (row.get("departamento") or {}).get("id"),
            "municipio_id": (row.get("municipio") or {}).get("id"),
        }
        for row in localidades_raw
    ]

    return {
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "source": API_ROOT,
        "provincias": provincias,
        "departamentos": departamentos,
        "municipios": municipios,
        "localidades": localidades,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Descarga catalogo Georef local")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/georef_catalog.json"),
        help="Ruta de salida del catalogo consolidado.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="Timeout por request en segundos.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    catalog = build_catalog(timeout=args.timeout)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False)

    print(
        f"catalogo georef guardado en {args.output} "
        f"(provincias={len(catalog['provincias'])}, "
        f"departamentos={len(catalog['departamentos'])}, "
        f"municipios={len(catalog['municipios'])}, "
        f"localidades={len(catalog['localidades'])})"
    )


if __name__ == "__main__":
    main()
