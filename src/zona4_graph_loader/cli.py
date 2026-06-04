from __future__ import annotations

import argparse

from zona4_graph_loader.pipeline.load_graph import run_load


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Carga y normalizacion de datos en Neo4j")
    parser.add_argument(
        "--clean-project",
        action="store_true",
        help="Limpia nodos y relaciones del proyecto (Persona, Lugar y AliasLugar) antes de cargar.",
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
    parser.add_argument(
        "--disable-georef-resolver",
        action="store_true",
        help="Desactiva la desambiguacion jerarquica basada en catalogo Georef local.",
    )
    parser.add_argument(
        "--georef-catalog-path",
        default="data/processed/georef_catalog.json",
        help="Ruta al catalogo Georef local (JSON consolidado).",
    )
    parser.add_argument(
        "--georef-min-score",
        type=float,
        default=0.76,
        help="Score minimo para aceptar una resolucion georeferenciada.",
    )
    parser.add_argument(
        "--georef-ambiguity-delta",
        type=float,
        default=0.02,
        help="Diferencia minima entre mejor y segundo candidato para evitar ambiguedades.",
    )
    parser.add_argument(
        "--sources-dir",
        default="data/sources",
        help="Directorio con archivos JSON de origen de datos directo para el pipeline.",
    )
    parser.add_argument(
        "--skip-direct-sources",
        action="store_true",
        help="No carga archivos JSON directos desde --sources-dir.",
    )
    parser.add_argument(
        "--validate-sources-only",
        action="store_true",
        help="Valida los archivos JSON de origen directo en el directorio de fuentes y sale sin inyectar datos en Neo4j.",
    )

    args = parser.parse_args()
    if args.clean_project and args.clean_all:
        parser.error("No se puede usar --clean-project y --clean-all al mismo tiempo")
    return args


def main() -> None:
    args = parse_args()
    if args.validate_sources_only:
        import sys
        from pathlib import Path
        from zona4_graph_loader.io.sources_ingestor import ALLOWED_SOURCE_KEYS, load_direct_sources
        
        sources_dir = Path(args.sources_dir)
        merged, files = load_direct_sources(sources_dir)
        print(f"Directorio de fuentes: {sources_dir}")
        print(f"Archivos detectados: {len(files)}")
        if files:
            print("Archivos directos cargados:")
            for path in files:
                print(f"  - {path}")
        print("Registros directos por colección:")
        for key in sorted(ALLOWED_SOURCE_KEYS):
            print(f"  {key}: {len(merged[key])}")
        sys.exit(0)

    run_load(args)


if __name__ == "__main__":
    main()
