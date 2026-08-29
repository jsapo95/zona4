from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, LiteralString, cast

from neo4j import GraphDatabase, Query

from zona4_graph_loader.builders.archivo_memoria import build_archivo_memoria_rows
from zona4_graph_loader.builders.base import CanonicalDataset
from zona4_graph_loader.builders.candidatos import build_v3_candidate_rows
from zona4_graph_loader.builders.ccds import build_ccd_rows
from zona4_graph_loader.builders.eaaf_lugares import build_eaaf_lugares_rows
from zona4_graph_loader.builders.juicios_condenados import build_juicios_condenados_rows
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
    CYPHER_LINK_ALIAS_PERSONA,
    CYPHER_LINK_DIRECCION_CCD_LUGAR,
    CYPHER_LINK_PERSONA_ENTIDAD,
    CYPHER_LINK_PERSONA_LUGAR_DYNAMIC,
    CYPHER_LINK_LUGAR_PARENT,
    CYPHER_UPSERT_ALIAS_LUGAR,
    CYPHER_UPSERT_ALIAS_PERSONA,
    CYPHER_UPSERT_CANDIDATO_MERGE,
    CYPHER_UPSERT_CARGO,
    CYPHER_UPSERT_DIRECCION_CCD,
    CYPHER_UPSERT_INSTITUCION,
    CYPHER_UPSERT_LUGARES,
    CYPHER_UPSERT_ORG,
    CYPHER_UPSERT_PERSONAS,
    CYPHER_UPSERT_PROFESION,
    CYPHER_UPSERT_PROTAGONISTAS,
    CYPHER_UPSERT_REL_FAMILIAR,
    CYPHER_UPSERT_REL_PERSONA,
)
from zona4_graph_loader.db.qa import run_qa_report
from zona4_graph_loader.db.writer import run_batches
from zona4_graph_loader.domain.identity_resolution import resolve_identities
from zona4_graph_loader.domain.roles import normalize_roles
from zona4_graph_loader.io.sources_ingestor import empty_canonical_dataset, load_direct_sources
from zona4_graph_loader.io.files import CCDS_PATH, DETALLES_PATH, NIETXS_PATH, read_json
from zona4_graph_loader.io.raw_files import read_raw_csv, read_raw_json


def _merge_datasets(dest: CanonicalDataset, src: CanonicalDataset) -> None:
    for key, rows in src.items():
        if rows:
            if key not in dest:
                dest[key] = []
            dest[key].extend(rows)


def contar_eventos_huerfanos(dataset: CanonicalDataset) -> List[Dict[str, Any]]:
    """Eventos espaciales cuyo lugar_key no existe como nodo :Lugar en el CDM.

    El Cypher de eventos hace MATCH sobre el lugar, así que estas filas se
    descartarían en silencio. Se reportan en vez de perderse.
    """
    lugar_keys = {
        l.get("lugar_key")
        for l in dataset.get("lugares", [])
        if l.get("tipo_entidad") == "Lugar"
    }
    return [
        e for e in dataset.get("eventos_espaciales", [])
        if e.get("lugar_key") not in lugar_keys
    ]


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

    if not args.skip_nuevas_fuentes:
        _merge_datasets(consolidated, build_eaaf_lugares_rows(read_raw_csv("eaaf_lugares.csv")))
        _merge_datasets(
            consolidated,
            build_archivo_memoria_rows(read_raw_json("archivo_memoria_san_martin.json")),
        )
        _merge_datasets(
            consolidated,
            build_juicios_condenados_rows(read_raw_json("juicios_lesa_humanidad_condenados.json")),
        )

    # 3. Load and merge direct static sources
    if not args.skip_direct_sources:
        sources_dir = Path(args.sources_dir)
        direct_rows, source_files = load_direct_sources(sources_dir)
        if source_files:
            print(f"sources_loaded: {len(source_files)} ({', '.join(p.name for p in source_files)})")
        else:
            print("sources_loaded: 0")
        _merge_datasets(consolidated, direct_rows)

    # 3.5 Reconcile identities across sources before writing anything
    for persona in consolidated.get("personas", []):
        persona["roles"] = normalize_roles(persona)

    identity_candidatos: List[Dict[str, Any]] = []
    if not args.skip_identity_resolution:
        identity_report = resolve_identities(consolidated)
        identity_candidatos = identity_report.candidatos
        print(
            f"identity_resolution: {len(identity_report.merges)} merges, "
            f"{len(identity_candidatos)} candidatos"
        )
        dump_path = Path("data/processed/identity_merges.json")
        dump_path.parent.mkdir(parents=True, exist_ok=True)
        with dump_path.open("w", encoding="utf-8") as f:
            json.dump(identity_report.merges, f, ensure_ascii=False, indent=2)

    if args.dump_cdm:
        dump_cdm_path = Path(args.dump_cdm)
        dump_cdm_path.parent.mkdir(parents=True, exist_ok=True)
        with dump_cdm_path.open("w", encoding="utf-8") as f:
            json.dump(consolidated, f, ensure_ascii=False, indent=2)
        print(f"dump_cdm: {dump_cdm_path}")

    # 4. Extract entities and relationships from the unificated CDM for Cypher execution
    personas_detalles = [
        p for p in consolidated.get("personas", []) if "NIETX" not in p["roles"]
    ]
    protagonistas = [
        p for p in consolidated.get("personas", []) if "NIETX" in p["roles"]
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

    eventos_huerfanos = contar_eventos_huerfanos(consolidated)
    if eventos_huerfanos:
        por_tipo: Dict[str, int] = {}
        for evento in eventos_huerfanos:
            tipo = evento.get("tipo_relacion", "DESCONOCIDO")
            por_tipo[tipo] = por_tipo.get(tipo, 0) + 1
        detalle = ", ".join(f"{k}={v}" for k, v in sorted(por_tipo.items()))
        print(f"Warning: {len(eventos_huerfanos)} eventos espaciales sin lugar resuelto ({detalle})")

    entidades = consolidated.get("entidades_contexto", [])
    orgs = [e for e in entidades if e.get("tipo_entidad") == "Org"]
    instituciones = [e for e in entidades if e.get("tipo_entidad") == "Institucion"]
    profesiones = [e for e in entidades if e.get("tipo_entidad") == "Profesion"]
    cargos = [e for e in entidades if e.get("tipo_entidad") == "Cargo"]
    alias_personas = [e for e in entidades if e.get("tipo_entidad") == "AliasPersona"]

    rel_contexto = [
        r for r in consolidated.get("relaciones_contexto", [])
        if r.get("tipo_relacion") != "IDENTIFICA_A"
    ]
    rel_alias_persona = [
        r for r in consolidated.get("relaciones_contexto", [])
        if r.get("tipo_relacion") == "IDENTIFICA_A"
    ]

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

        # Ingest context entities (V1.2)
        run_batches(session, CYPHER_UPSERT_ORG, orgs, "orgs", BATCH_SIZE)
        run_batches(session, CYPHER_UPSERT_INSTITUCION, instituciones, "instituciones", BATCH_SIZE)
        run_batches(session, CYPHER_UPSERT_PROFESION, profesiones, "profesiones", BATCH_SIZE)
        run_batches(session, CYPHER_UPSERT_CARGO, cargos, "cargos", BATCH_SIZE)
        run_batches(session, CYPHER_UPSERT_ALIAS_PERSONA, alias_personas, "alias_personas", BATCH_SIZE)
        run_batches(session, CYPHER_LINK_PERSONA_ENTIDAD, rel_contexto, "rel_contexto", BATCH_SIZE)
        run_batches(session, CYPHER_LINK_ALIAS_PERSONA, rel_alias_persona, "rel_alias_persona", BATCH_SIZE)

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
        if not args.skip_identity_resolution:
            run_batches(
                session, CYPHER_UPSERT_CANDIDATO_MERGE, identity_candidatos, "identity_candidatos", BATCH_SIZE
            )

        # Run QA closure report
        if not args.skip_qa_report:
            run_qa_report(session, include_candidates=not args.skip_v3_candidates)

    driver.close()
