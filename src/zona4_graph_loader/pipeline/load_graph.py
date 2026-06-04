from __future__ import annotations

import argparse
from pathlib import Path
from typing import LiteralString, cast

from neo4j import GraphDatabase, Query

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
from zona4_graph_loader.io.extensions import load_extension_collections
from zona4_graph_loader.io.files import CCDS_PATH, DETALLES_PATH, NIETXS_PATH, read_json


def run_load(args: argparse.Namespace) -> None:
    # 1. Read input JSON files from data/processed
    detalles = read_json(DETALLES_PATH)
    nietxs = read_json(NIETXS_PATH)
    ccds = read_json(CCDS_PATH)

    # 2. Build Base Persons (Victims) and Grandkids (Nietxs)
    detalles_personas = build_detalles_rows(detalles)
    protagonistas = build_nietx_protagonistas(nietxs)

    # 3. Build Interpersonal relationships
    rel_familiares = build_nietx_rel_rows(nietxs)
    rel_personas = build_detalles_rel_rows(detalles)

    # 4. Build Geographic Place Layers
    lugar_layer = (
        build_lugar_layer_rows(
            detalles,
            use_georef=not args.disable_georef_resolver,
            georef_catalog_path=Path(args.georef_catalog_path),
            georef_min_score=args.georef_min_score,
            georef_ambiguity_delta=args.georef_ambiguity_delta,
        )
        if not args.skip_lugares
        else {
            "lugares": [],
            "aliases": [],
            "direcciones": [],
            "direccion_lugar_links": [],
            "parents": [],
            "persona_lugar_links": [],
        }
    )

    # 5. Build Clandestine Detention Center (CCD) Layers
    ccd_layer = build_ccd_rows(
        detalles,
        ccds,
        existing_lugar_keys={row["lugar_key"] for row in lugar_layer["lugares"]},
        use_georef=not args.disable_georef_resolver,
        georef_catalog_path=Path(args.georef_catalog_path),
        georef_min_score=args.georef_min_score,
        georef_ambiguity_delta=args.georef_ambiguity_delta,
    )

    # 6. Consolidate place, parent, address, and temporal link layers
    if not args.skip_lugares:
        lugar_layer["lugares"].extend(ccd_layer["lugares"])
        lugar_layer["direcciones"].extend(ccd_layer["direcciones"])
        lugar_layer["direccion_lugar_links"].extend(ccd_layer["direccion_lugar_links"])
        lugar_layer["parents"].extend(ccd_layer["parents"])
        lugar_layer["persona_lugar_links"].extend(ccd_layer["persona_lugar_links"])

    # 7. Merge external/manual extension collections
    if not args.skip_extensions:
        extension_rows, extension_files = load_extension_collections(Path(args.extensions_dir))
        if extension_files:
            print(f"extensions_loaded: {len(extension_files)} ({', '.join(p.name for p in extension_files)})")
        else:
            print("extensions_loaded: 0")

        detalles_personas.extend(extension_rows["personas_detalles"])
        protagonistas.extend(extension_rows["protagonistas"])
        rel_familiares.extend(extension_rows["rel_familiares"])
        rel_personas.extend(extension_rows["rel_personas"])

        if not args.skip_lugares:
            lugar_layer["lugares"].extend(extension_rows["lugares"])
            lugar_layer["aliases"].extend(extension_rows["aliases"])
            lugar_layer["direcciones"].extend(extension_rows["direcciones"])
            lugar_layer["parents"].extend(extension_rows["parents"])
            lugar_layer["persona_lugar_links"].extend(extension_rows["persona_lugar_links"])
            lugar_layer["direccion_lugar_links"].extend(extension_rows["direccion_lugar_links"])

    # 8. Build Safe Place Merges and Identity Reconciliations
    safe_place_merges = (
        build_safe_place_merge_rows(lugar_layer)
        if (not args.skip_lugares and args.apply_safe_place_merges)
        else []
    )
    v3_candidates = build_v3_candidate_rows(detalles_personas, rel_familiares, rel_personas)

    # 9. Ingest into Neo4j
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
        run_batches(session, CYPHER_UPSERT_PERSONAS, detalles_personas, "personas_detalles", BATCH_SIZE)
        run_batches(session, CYPHER_UPSERT_PROTAGONISTAS, protagonistas, "protagonistas_nietx", BATCH_SIZE)

        # Ingest Family and Interpersonal relationships
        run_batches(session, CYPHER_UPSERT_REL_FAMILIAR, rel_familiares, "relaciones_familiares_nietx", BATCH_SIZE)
        run_batches(session, CYPHER_UPSERT_REL_PERSONA, rel_personas, "relaciones_detalles", BATCH_SIZE)

        # Ingest Geographic/CCD layers
        if not args.skip_lugares:
            run_batches(session, CYPHER_UPSERT_LUGARES, lugar_layer["lugares"], "lugares", BATCH_SIZE)
            run_batches(session, CYPHER_LINK_LUGAR_PARENT, lugar_layer["parents"], "lugar_parte_de", BATCH_SIZE)
            run_batches(session, CYPHER_UPSERT_ALIAS_LUGAR, lugar_layer["aliases"], "alias_lugar", BATCH_SIZE)
            run_batches(session, CYPHER_UPSERT_DIRECCION_CCD, lugar_layer["direcciones"], "direcciones_ccd", BATCH_SIZE)
            run_batches(session, CYPHER_LINK_DIRECCION_CCD_LUGAR, lugar_layer["direccion_lugar_links"], "direccion_ccd_lugar", BATCH_SIZE)
            
            # Dynamic direct events (e.g. SECUESTRADO_EN, NACIO_EN)
            run_batches(
                session,
                CYPHER_LINK_PERSONA_LUGAR_DYNAMIC,
                lugar_layer["persona_lugar_links"],
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
