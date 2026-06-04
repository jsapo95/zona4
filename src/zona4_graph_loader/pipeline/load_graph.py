from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List, LiteralString, cast

from neo4j import GraphDatabase, Query

from zona4_graph_loader.builders.base import CanonicalDataset
from zona4_graph_loader.builders.candidatos import build_v3_candidate_rows
from zona4_graph_loader.builders.ccds import build_ccd_rows
from zona4_graph_loader.builders.lugares import build_lugar_layer_rows, build_safe_place_merge_rows
from zona4_graph_loader.builders.personas import build_detalles_rows, build_nietx_protagonistas
from zona4_graph_loader.builders.relaciones import build_detalles_rel_rows, build_nietx_rel_rows
from zona4_graph_loader.config import get_config
from zona4_graph_loader.constants import BATCH_SIZE
from zona4_graph_loader.db.cypher import (
    CONSTRAINTS,
    CYPHER_APPLY_SAFE_PLACE_MERGES,
    CYPHER_CLEAN_ALL,
    CYPHER_CLEAN_PROJECT,
    CYPHER_LINK_DIRECCION_CCD_LUGAR,
    CYPHER_LINK_PERSONA_LUGAR_DYNAMIC,
    CYPHER_LINK_LUGAR_PARENT,
    CYPHER_UPSERT_ALIAS_LUGAR,
    CYPHER_UPSERT_CANDIDATO_MERGE,
    CYPHER_UPSERT_DIRECCION_CCD,
    CYPHER_UPSERT_LUGARES,
    CYPHER_UPSERT_PERSONAS,
    CYPHER_UPSERT_PROTAGONISTAS,
    CYPHER_UPSERT_REL_FAMILIAR,
    CYPHER_UPSERT_REL_PERSONA,
)
from zona4_graph_loader.db.qa import run_qa_report
from zona4_graph_loader.db.writer import run_batches
from zona4_graph_loader.io.sources_ingestor import empty_canonical_dataset, load_direct_sources
from zona4_graph_loader.io.files import CCDS_PATH, DETALLES_PATH, NIETXS_PATH, read_json


def _merge_datasets(dest: CanonicalDataset, src: CanonicalDataset) -> None:
    for key, rows in src.items():
        if rows:
            if key not in dest:
                dest[key] = []
            dest[key].extend(rows)


def run_load(args: argparse.Namespace) -> None:
    # 1. Read input JSON files from data/sources
    detalles = read_json(DETALLES_PATH)
    nietxs = read_json(NIETXS_PATH)
    ccds = read_json(CCDS_PATH)

    # Consolidated CDM container
    consolidated = empty_canonical_dataset()

    # 2. Run builders (convert inputs to unificated CDM)
    _merge_datasets(consolidated, build_detalles_rows(detalles))
    _merge_datasets(consolidated, build_nietx_protagonistas(nietxs))
    _merge_datasets(consolidated, build_nietx_rel_rows(nietxs))
    _merge_datasets(consolidated, build_detalles_rel_rows(detalles))

    if not args.skip_lugares:
        lugar_layer = build_lugar_layer_rows(
            detalles,
            use_georef=not args.disable_georef_resolver,
            georef_catalog_path=Path(args.georef_catalog_path),
            georef_min_score=args.georef_min_score,
            georef_ambiguity_delta=args.georef_ambiguity_delta,
        )
        _merge_datasets(consolidated, lugar_layer)

        existing_lugar_keys = {
            row["lugar_key"]
            for row in consolidated.get("lugares", [])
            if row.get("tipo_entidad") == "Lugar"
        }

        ccd_layer = build_ccd_rows(
            detalles,
            ccds,
            existing_lugar_keys=existing_lugar_keys,
            use_georef=not args.disable_georef_resolver,
            georef_catalog_path=Path(args.georef_catalog_path),
            georef_min_score=args.georef_min_score,
            georef_ambiguity_delta=args.georef_ambiguity_delta,
        )
        _merge_datasets(consolidated, ccd_layer)

    # 3. Load and merge direct static sources
    if not args.skip_direct_sources:
        sources_dir = Path(args.sources_dir)
        direct_rows, source_files = load_direct_sources(sources_dir)
        if source_files:
            print(f"sources_loaded: {len(source_files)} ({', '.join(p.name for p in source_files)})")
        else:
            print("sources_loaded: 0")
        _merge_datasets(consolidated, direct_rows)

    # 4. Extract entities and relationships from the unificated CDM for Cypher execution
    personas_detalles = [
        p for p in consolidated.get("personas", []) if not p.get("es_nietx")
    ]
    protagonistas = [
        p for p in consolidated.get("personas", []) if p.get("es_nietx")
    ]

    rel_familiares = [
        r for r in consolidated.get("relaciones_interpersonales", [])
        if r.get("fuente") == "nietxs_relacion"
    ]
    rel_personas = [
        r for r in consolidated.get("relaciones_interpersonales", [])
        if r.get("fuente") != "nietxs_relacion"
    ]

    lugares_nodos = [
        l for l in consolidated.get("lugares", []) if l.get("tipo_entidad") == "Lugar"
    ]
    aliases_nodos = [
        l for l in consolidated.get("lugares", []) if l.get("tipo_entidad") == "AliasLugar"
    ]
    direcciones_nodos = [
        l for l in consolidated.get("lugares", []) if l.get("tipo_entidad") == "DireccionCCD"
    ]

    parents = [
        j for j in consolidated.get("jerarquias", []) if j.get("tipo_relacion") == "PARTE_DE"
    ]
    direccion_lugar_links = [
        j for j in consolidated.get("jerarquias", []) if j.get("tipo_relacion") == "UBICADA_EN"
    ]

    persona_lugar_links = consolidated.get("eventos_espaciales", [])

    # 5. Build Safe Place Merges and Identity Reconciliations
    safe_place_merges = (
        build_safe_place_merge_rows(consolidated)
        if (not args.skip_lugares and args.apply_safe_place_merges)
        else []
    )
    v3_candidates = build_v3_candidate_rows(personas_detalles, rel_familiares, rel_personas)

    # 6. Ingest into Neo4j
    cfg = get_config()
    driver = GraphDatabase.driver(cfg.uri, auth=(cfg.username, cfg.password))

    with driver.session(database=cfg.database) as session:
        # DB Cleaning
        if args.clean_all:
            session.run(Query(cast(LiteralString, CYPHER_CLEAN_ALL))).consume()
            print("clean_all: ok")
        elif args.clean_project:
            session.run(Query(cast(LiteralString, CYPHER_CLEAN_PROJECT))).consume()
            print("clean_project: ok")

        # Create constraints and indexes
        for statement in CONSTRAINTS:
            try:
                session.run(Query(cast(LiteralString, statement))).consume()
            except Exception as e:
                err_str = str(e)
                if "Enterprise Edition" in err_str or "existence constraint" in err_str.lower():
                    print(f"Warning: Skipping constraint (requires Enterprise Edition): {statement}")
                else:
                    raise e

        # Ingest Person roles
        run_batches(session, CYPHER_UPSERT_PERSONAS, personas_detalles, "personas_detalles", BATCH_SIZE)
        run_batches(session, CYPHER_UPSERT_PROTAGONISTAS, protagonistas, "protagonistas_nietx", BATCH_SIZE)

        # Ingest Family and Interpersonal relationships
        run_batches(session, CYPHER_UPSERT_REL_FAMILIAR, rel_familiares, "relaciones_familiares_nietx", BATCH_SIZE)
        run_batches(session, CYPHER_UPSERT_REL_PERSONA, rel_personas, "relaciones_detalles", BATCH_SIZE)

        # Ingest Geographic/CCD layers
        if not args.skip_lugares:
            run_batches(session, CYPHER_UPSERT_LUGARES, lugares_nodos, "lugares", BATCH_SIZE)
            run_batches(session, CYPHER_LINK_LUGAR_PARENT, parents, "lugar_parte_de", BATCH_SIZE)
            run_batches(session, CYPHER_UPSERT_ALIAS_LUGAR, aliases_nodos, "alias_lugar", BATCH_SIZE)
            run_batches(session, CYPHER_UPSERT_DIRECCION_CCD, direcciones_nodos, "direcciones_ccd", BATCH_SIZE)
            run_batches(session, CYPHER_LINK_DIRECCION_CCD_LUGAR, direccion_lugar_links, "direccion_ccd_lugar", BATCH_SIZE)
            
            # Dynamic direct events (e.g. SECUESTRADO_EN, NACIO_EN)
            run_batches(
                session,
                CYPHER_LINK_PERSONA_LUGAR_DYNAMIC,
                persona_lugar_links,
                "persona_lugar_eventos_directos",
                BATCH_SIZE,
            )

            # Apply safe city/toponym merges
            if args.apply_safe_place_merges:
                run_batches(
                    session,
                    CYPHER_APPLY_SAFE_PLACE_MERGES,
                    safe_place_merges,
                    "safe_place_merges_aplicados",
                    BATCH_SIZE,
                )

        # Ingest Candidate merges
        if not args.skip_v3_candidates:
            run_batches(session, CYPHER_UPSERT_CANDIDATO_MERGE, v3_candidates, "v3_candidatos_merge", BATCH_SIZE)

        # Run QA closure report
        if not args.skip_qa_report:
            run_qa_report(session, include_candidates=not args.skip_v3_candidates)

    driver.close()
