from __future__ import annotations

import argparse

from zona4_graph_loader.pipeline.load_graph import run_load


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Carga y normalizacion de datos en Neo4j Aura")
    parser.add_argument(
        "--clean-project",
        action="store_true",
        help="Limpia solo nodos y relaciones del proyecto (Persona, CasoNietx, Evento) antes de cargar.",
    )
    parser.add_argument(
        "--clean-all",
        action="store_true",
        help="Limpia todo el grafo antes de cargar.",
    )
    parser.add_argument(
        "--skip-v3-candidates",
        action="store_true",
        help="No crea relaciones CANDIDATO_MERGE de reconciliacion asistida.",
    )
    parser.add_argument(
        "--skip-qa-report",
        action="store_true",
        help="No imprime el reporte QA de cierre al finalizar la carga.",
    )
    parser.add_argument(
        "--skip-listado-paginas",
        action="store_true",
        help="No integra data/listado_paginas.json (PaginaListado y relacion LISTADA_EN).",
    )
    parser.add_argument(
        "--skip-lugares",
        action="store_true",
        help="No construye la capa de Lugar/AliasLugar ni enlaces con Persona/Evento.",
    )
    parser.add_argument(
        "--apply-safe-place-merges",
        action="store_true",
        help="Aplica merges automaticos conservadores de nodos Lugar tipo CIUDAD (solo typos/variantes seguras).",
    )

    args = parser.parse_args()
    if args.clean_project and args.clean_all:
        parser.error("No se puede usar --clean-project y --clean-all al mismo tiempo")
    return args


def main() -> None:
    args = parse_args()
    run_load(args)
