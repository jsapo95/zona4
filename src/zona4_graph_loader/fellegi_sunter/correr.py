"""Corre el modelo completo sobre las fuentes del repo, sin Neo4j.

    PYTHONPATH=src .venv/Scripts/python -m zona4_graph_loader.fellegi_sunter.correr

Escribe en `data/processed/fellegi_sunter/` (fuera de git, porque tiene
nombres de personas):

- `pares.csv`: un par por fila, con el nivel de cada campo, el peso de cada
  campo, el peso total, P(M|γ) y la decisión.
- `parametros.json`: por estrato (par de fuentes), cuántos pares hay, π, m y
  u por campo y nivel, los umbrales y el resultado de cada inicio del EM.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

from zona4_graph_loader.fellegi_sunter.comparaciones import CAMPOS, NIVELES
from zona4_graph_loader.fellegi_sunter.decision import calcular_umbrales, decidir
from zona4_graph_loader.fellegi_sunter.em import (
    Conteos,
    Parametros,
    ajustar_em_varios_inicios,
    peso,
    pesos_por_campo,
    probabilidad_match,
)
from zona4_graph_loader.fellegi_sunter.pares import Patron, Registro, construir_registros, estrato, generar_pares

SALIDA_POR_DEFECTO = Path("data/processed/fellegi_sunter")
NUM_NIVELES = [len(NIVELES[campo]) for campo in CAMPOS]


def _nombre_nivel(k: int, nivel: Any) -> str:
    return "falta" if nivel is None else NIVELES[CAMPOS[k]][nivel]


def ajustar_estratos(
    pares: List[Tuple[Registro, Registro, Patron]],
    mu: float,
    lam: float,
    inicios_aleatorios: int,
    semilla: int,
) -> Dict[Tuple[str, str], Dict[str, Any]]:
    """Un ajuste del EM y unos umbrales por cada par de fuentes."""
    conteos_por_estrato: Dict[Tuple[str, str], Conteos] = defaultdict(Counter)
    for a, b, gamma in pares:
        conteos_por_estrato[estrato(a, b)][gamma] += 1

    resultado = {}
    for clave, conteos in sorted(conteos_por_estrato.items()):
        mejor, ajustes = ajustar_em_varios_inicios(
            conteos, NUM_NIVELES, inicios_aleatorios=inicios_aleatorios, semilla=semilla
        )
        resultado[clave] = {
            "conteos": conteos,
            "parametros": mejor,
            "ajustes": ajustes,
            "umbrales": calcular_umbrales(conteos, mejor, mu, lam),
        }
    return resultado


def _parametros_json(params: Parametros) -> Dict[str, Any]:
    return {
        "pi": params.pi,
        "m": {c: dict(zip(NIVELES[c], params.m[k])) for k, c in enumerate(CAMPOS)},
        "u": {c: dict(zip(NIVELES[c], params.u[k])) for k, c in enumerate(CAMPOS)},
        "objetivo": params.objetivo,
        "iteraciones": params.iteraciones,
        "convergio": params.convergio,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Modelo de Fellegi–Sunter sobre las fuentes del repo")
    parser.add_argument("--mu", type=float, default=0.01, help="Tasa máxima estimada de vínculos falsos.")
    parser.add_argument("--lambda", dest="lam", type=float, default=0.01,
                        help="Tasa máxima estimada de vínculos perdidos.")
    parser.add_argument("--inicios", type=int, default=10, help="Inicios aleatorios del EM, además del por defecto.")
    parser.add_argument("--semilla", type=int, default=0)
    parser.add_argument("--salida", default=str(SALIDA_POR_DEFECTO))
    args = parser.parse_args()

    # Import diferido: el loader importa neo4j, que este módulo no necesita
    # para nada más.
    from zona4_graph_loader.cli import build_parser
    from zona4_graph_loader.pipeline.load_graph import construir_cdm

    dataset = construir_cdm(build_parser().parse_args([]))
    registros = construir_registros(dataset)
    pares = list(generar_pares(registros))
    estratos = ajustar_estratos(pares, args.mu, args.lam, args.inicios, args.semilla)

    salida = Path(args.salida)
    salida.mkdir(parents=True, exist_ok=True)
    (salida / ".gitignore").write_text("*\n", encoding="utf-8")

    nombres = {p["persona_key"]: p.get("nombre") for p in dataset.get("personas") or []}
    decisiones: Counter = Counter()
    with (salida / "pares.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["clave_a", "clave_b", "fuente_a", "fuente_b", "nombre_a", "nombre_b"]
            + [f"nivel_{c}" for c in CAMPOS]
            + [f"peso_{c}" for c in CAMPOS]
            + ["peso", "prob_match", "decision"]
        )
        for a, b, gamma in pares:
            ajuste = estratos[estrato(a, b)]
            params = ajuste["parametros"]
            w = peso(gamma, params)
            decision = decidir(w, ajuste["umbrales"])
            decisiones[(estrato(a, b), decision)] += 1
            writer.writerow(
                [a.clave, b.clave, a.fuente, b.fuente, nombres.get(a.clave), nombres.get(b.clave)]
                + [_nombre_nivel(k, nivel) for k, nivel in enumerate(gamma)]
                + ["" if x is None else round(x, 4) for x in pesos_por_campo(gamma, params)]
                + [round(w, 4), round(probabilidad_match(gamma, params), 6), decision]
            )

    resumen = {
        "registros_por_fuente": dict(Counter(r.fuente for r in registros)),
        "mu": args.mu,
        "lambda": args.lam,
        "estratos": {
            "|".join(clave): {
                "pares": sum(e["conteos"].values()),
                "patrones_distintos": len(e["conteos"]),
                "parametros": _parametros_json(e["parametros"]),
                "umbrales": vars(e["umbrales"]),
                "decisiones": {d: decisiones[(clave, d)] for d in ("vincular", "revisar", "no_vincular")},
                "objetivo_por_inicio": [p.objetivo for p in e["ajustes"]],
                "pi_por_inicio": [p.pi for p in e["ajustes"]],
            }
            for clave, e in estratos.items()
        },
    }
    with (salida / "parametros.json").open("w", encoding="utf-8") as f:
        json.dump(resumen, f, ensure_ascii=False, indent=2, default=str)

    print(f"registros: {len(registros)}  pares: {len(pares)}  estratos: {len(estratos)}")
    for clave, e in resumen["estratos"].items():
        print(f"  {clave}: {e['pares']} pares, pi={e['parametros']['pi']:.4f}, {e['decisiones']}")
    print(f"salida: {salida}")


if __name__ == "__main__":
    main()
