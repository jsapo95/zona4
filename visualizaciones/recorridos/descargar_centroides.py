#!/usr/bin/env python3
"""Descarga los centroides de Georef para ubicar en el mapa los lugares del grafo.

El catálogo `data/processed/georef_catalog.json` que usa el loader trae
nombres e ids pero no coordenadas. Para dibujar un lugar resuelto a nivel
localidad, departamento o provincia usamos el centroide que publica Georef
para esa unidad (la ubicación es la de la unidad, no la de un domicilio).

Se corre una sola vez; el resultado queda versionado en
`visualizaciones/recorridos/datos/centroides_georef.json`.
"""

from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

API_ROOT = "https://apis.datos.gob.ar/georef/api"
SALIDA = Path(__file__).parent / "datos" / "centroides_georef.json"


def _fetch_json(url: str, timeout: int) -> Dict[str, Any]:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_all(
    resource: str, campos: str, timeout: int, page_size: int = 5000, **filtros: str
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    inicio = 0
    total = None
    while total is None or inicio < total:
        params = {"campos": campos, "max": str(page_size), "inicio": str(inicio), **filtros}
        payload = _fetch_json(f"{API_ROOT}/{resource}?{urllib.parse.urlencode(params)}", timeout)
        batch = payload.get(resource, [])
        rows.extend(batch)
        total = int(payload.get("total", len(rows)))
        inicio += page_size
        if not batch:
            break
    return rows


def _plano(row: Dict[str, Any]) -> Dict[str, Any]:
    centroide = row.get("centroide") or {}
    return {
        "id": row.get("id"),
        "nombre": row.get("nombre"),
        "provincia": (row.get("provincia") or {}).get("nombre"),
        "departamento": (row.get("departamento") or {}).get("nombre"),
        "lat": round(centroide["lat"], 5),
        "lon": round(centroide["lon"], 5),
    }


def build(timeout: int) -> Dict[str, Any]:
    provincias = fetch_all("provincias", "id,nombre,centroide", timeout)
    return {
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "source": API_ROOT,
        "provincias": [_plano(r) for r in provincias],
        "departamentos": [
            _plano(r) for r in fetch_all("departamentos", "id,nombre,centroide,provincia.nombre", timeout)
        ],
        "municipios": [
            _plano(r) for r in fetch_all("municipios", "id,nombre,centroide,provincia.nombre", timeout)
        ],
        "localidades": [
            _plano(r)
            for r in fetch_all(
                "localidades", "id,nombre,centroide,provincia.nombre,departamento.nombre", timeout
            )
        ],
        # Asentamientos (BAHRA): barrios y parajes que no son localidad, p.ej.
        # Don Torcuato o José León Suárez. Se usan sólo si no hay localidad.
        # La API no pagina más allá de 10.000 resultados: se pide por provincia.
        "asentamientos": [
            _plano(r)
            for p in provincias
            for r in fetch_all(
                "asentamientos", "id,nombre,centroide,provincia.nombre,departamento.nombre", timeout,
                provincia=p["id"],
            )
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, default=SALIDA)
    parser.add_argument("--timeout", type=int, default=60)
    args = parser.parse_args()

    catalogo = build(args.timeout)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        json.dump(catalogo, f, ensure_ascii=False, separators=(",", ":"))
    conteos = ", ".join(f"{k}={len(v)}" for k, v in catalogo.items() if isinstance(v, list))
    print(f"centroides guardados en {args.output} ({conteos})")


if __name__ == "__main__":
    main()
